// AERIS's on-device brain: a small LLM (Qwen3 1.7B GGUF via llama.cpp) that
// turns what you said into ONE contract object — tool_call / ask / reply /
// plan / escalate (aeris_brain/docs/AERIS_BRAIN_V2.md).
//
// The rule router stays the instant path. The brain is asked only when the
// router has nothing (its "search the web?" fallback) or when the brain itself
// just asked a question. Modes (Settings → Brain):
//   off     never used
//   shadow  the router acts; the brain decides silently afterwards and both are
//           logged — measures it on YOUR real commands before trusting it
//   on      the brain handles what the router can't (default)
//
// Model file: any *.gguf in the app's external files dir —
//   adb push model.gguf /sdcard/Android/data/com.aeris.aeris_assistant/files/models/
// Until your own model is trained, the stock Qwen3-1.7B-Q4_K_M works (zero-shot,
// grammar-constrained, so its output is always valid JSON).
import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart' show rootBundle;
import 'package:path_provider/path_provider.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../../core/models.dart';
import '../memory_search.dart';
import 'contract.dart';
import 'grammar.dart';
import 'prompt.dart';
import 'runtime.dart';

enum BrainMode { off, shadow, on }

enum BrainStatus { noModel, idle, loading, ready, error }

class BrainDecision {
  const BrainDecision(this.text, this.raw, this.obj, this.errors, this.gen, this.totalMs);
  final String text; // what the user said
  final String raw; // model output
  final Map<String, dynamic>? obj;
  final List<String> errors;
  final BrainGeneration? gen;
  final int totalMs;

  bool get valid => obj != null && errors.isEmpty;
  String? get type => obj?['type'] as String?;

  /// One line for logs and the Brain screen.
  String get summary {
    if (!valid) return 'invalid: ${errors.isEmpty ? raw : errors.join('; ')}';
    return switch (type) {
      'tool_call' => [
          for (final c in obj!['calls'] as List) '${c['name']}(${jsonEncode(c['args'])})'
        ].join(' + '),
      'ask' => 'ask: ${obj!['text']}',
      'reply' => 'reply: ${obj!['text']}',
      'plan' => 'plan: ${obj!['goal']}',
      _ => 'escalate(${obj!['reason']}): ${obj!['query']}',
    };
  }
}

class AerisBrain {
  /// The overrides exist for tests (no plugins there): a fake runtime, the
  /// tools JSON as a string, and plain folders instead of path_provider's.
  AerisBrain({BrainRuntime? runtime, this.toolsJsonOverride, this.supportDirOverride, this.modelDirOverride})
      : _runtime = runtime ?? LlamaRuntime();

  final BrainRuntime _runtime;
  final String? toolsJsonOverride;
  final String? supportDirOverride;
  final String? modelDirOverride;

  static const _kMode = 'brain.mode', _kThreads = 'brain.threads';
  static const idleUnload = Duration(minutes: 10);
  static const historyTtl = Duration(minutes: 2);
  static const contextSize = 2048; // ~1k system prompt + a few turns + 256 out

  final ValueNotifier<BrainMode> mode = ValueNotifier(BrainMode.on);
  final ValueNotifier<BrainStatus> status = ValueNotifier(BrainStatus.idle);
  final ValueNotifier<String> statusText = ValueNotifier('');

  Map<String, ToolSpec>? _tools;
  String? _modelPath;
  int threads = 4;
  final List<Turn> _history = [];
  DateTime _lastTurn = DateTime.fromMillisecondsSinceEpoch(0);
  Timer? _idle;
  Future<void> _lock = Future.value();
  String? _warmFor; // base prompt the KV prefix was built for
  Future<bool>? _loading;
  String? _grammar;

  String? get modelPath => _modelPath;
  Map<String, ToolSpec> get tools => _tools ?? const {};
  bool get hasModel => _modelPath != null;

  /// Worth asking? (mode allows it and a model file exists)
  bool get enabled => mode.value == BrainMode.on && hasModel;

  // ── settings ────────────────────────────────────────────────────────
  Future<void> load() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final savedMode = prefs.getString(_kMode);
      mode.value = BrainMode.values.firstWhere((m) => m.name == savedMode, orElse: () => BrainMode.on);
      threads = prefs.getInt(_kThreads) ?? 4;
    } catch (_) {/* first run, or prefs unavailable in tests: keep defaults */}
    await _ensureTools();
    await refreshModel();
  }

  /// Re-scan the models folder (after an adb push).
  Future<void> refreshModel() async {
    _modelPath = (await findModels()).firstOrNull?.path;
    if (_modelPath == null) {
      status.value = BrainStatus.noModel;
      statusText.value = 'No model file';
    } else if (status.value == BrainStatus.noModel) {
      status.value = BrainStatus.idle;
      statusText.value = '';
    }
  }

  Future<void> setMode(BrainMode newMode) async {
    mode.value = newMode;
    try {
      await (await SharedPreferences.getInstance()).setString(_kMode, newMode.name);
    } catch (_) {}
    if (newMode == BrainMode.off) await unload();
  }

  Future<void> setThreads(int threadCount) async {
    threads = threadCount;
    try {
      await (await SharedPreferences.getInstance()).setInt(_kThreads, threadCount);
    } catch (_) {}
    await unload(); // thread count is fixed at load time
  }

  Future<Directory> modelDir() async {
    if (modelDirOverride != null) return Directory(modelDirOverride!);
    final ext = await getExternalStorageDirectory();
    return Directory('${(ext ?? await getApplicationSupportDirectory()).path}/models');
  }

  /// Newest *.gguf first.
  Future<List<File>> findModels() async {
    final folder = await modelDir();
    if (!await folder.exists()) return const [];
    final models = [
      await for (final entry in folder.list())
        if (entry is File && entry.path.toLowerCase().endsWith('.gguf')) entry
    ];
    models.sort((a, b) => b.statSync().modified.compareTo(a.statSync().modified));
    return models;
  }

  Future<void> _ensureTools() async {
    _tools ??= parseTools(toolsJsonOverride ?? await rootBundle.loadString('assets/brain/tools.json'));
  }

  // ── prompt pieces ───────────────────────────────────────────────────
  /// App language → the language rule the model was trained with.
  static String langRule(Lang appLanguage) => appLanguage == Lang.hinglish ? 'match' : 'english';

  /// All tools, registry order: a byte-stable prefix whose KV cache is
  /// computed once and reused for every turn.
  String fixedPrompt(Lang appLanguage) => basePrompt(tools.values.toList(), lang: langRule(appLanguage));

  String grammar() => _grammar ??= contractGrammar(tools.values.toList()).toGbnf();

  /// "Friday 17 October 2026, 18:40" — the training format.
  static String nowText(DateTime time) {
    const days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'];
    const months = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];
    String twoDigits(int n) => n.toString().padLeft(2, '0');
    return '${days[time.weekday - 1]} ${time.day} ${months[time.month - 1]} ${time.year}, '
        '${twoDigits(time.hour)}:${twoDigits(time.minute)}';
  }

  // ── lifecycle ───────────────────────────────────────────────────────
  /// Loads the model (if needed) and caches the fixed prompt. Concurrent
  /// callers share one load.
  Future<bool> ensureReady(Lang appLanguage) async {
    await _ensureTools();
    if (_runtime.isLoaded && _warmFor == fixedPrompt(appLanguage)) {
      _restartIdleTimer();
      return true;
    }
    return _loading ??= _load(appLanguage).whenComplete(() => _loading = null);
  }

  Future<bool> _load(Lang appLanguage) async {
    final path = _modelPath ?? (await findModels()).firstOrNull?.path;
    if (path == null || !await File(path).exists()) {
      status.value = BrainStatus.noModel;
      statusText.value = 'No model file';
      return false;
    }
    _modelPath = path;
    try {
      status.value = BrainStatus.loading;
      final stopwatch = Stopwatch()..start();
      if (!_runtime.isLoaded) {
        statusText.value = 'Loading model…';
        await _runtime.load(path, threads: threads, contextSize: contextSize);
      }
      statusText.value = 'Preparing prompt…';
      final fixed = fixedPrompt(appLanguage);
      final reusedCache = await _runtime.warmPrefix(cachedPrefix(fixed), await _promptCacheFile(path, fixed));
      _warmFor = fixed;
      status.value = BrainStatus.ready;
      final seconds = (stopwatch.elapsedMilliseconds / 1000).toStringAsFixed(1);
      statusText.value = 'Ready in $seconds s${reusedCache ? ' (cached prompt)' : ''}';
      _restartIdleTimer();
      return true;
    } catch (e) {
      status.value = BrainStatus.error;
      statusText.value = '$e';
      await _runtime.unload();
      return false;
    }
  }

  /// One cache file per (model file, prompt) — a new model or a changed
  /// prompt can never load a stale KV state.
  Future<String> _promptCacheFile(String modelPath, String prompt) async {
    final modelInfo = await File(modelPath).stat();
    final key = stableHash('$modelPath|${modelInfo.size}|${modelInfo.modified.millisecondsSinceEpoch}|$prompt');
    return '${await _supportFolder()}/brain_cache/$key.kv';
  }

  /// FNV-1a 64-bit, printed as two unsigned 32-bit halves (Dart ints are
  /// signed — a minus sign in a file name once broke VoiceCache).
  static String stableHash(String text) {
    var hash = 0xcbf29ce484222325;
    for (final byte in utf8.encode(text)) {
      hash = (hash ^ byte) * 0x100000001b3;
    }
    final high = (hash >> 32) & 0xffffffff, low = hash & 0xffffffff;
    return '${high.toRadixString(16)}${low.toRadixString(16).padLeft(8, '0')}';
  }

  void _restartIdleTimer() {
    _idle?.cancel();
    _idle = Timer(idleUnload, unload);
  }

  /// Frees the model's ~1.8 GB; reloading is a few seconds (mmap + cached prompt).
  Future<void> unload() async {
    _idle?.cancel();
    _warmFor = null;
    await _runtime.unload();
    if (status.value == BrainStatus.ready || status.value == BrainStatus.loading) {
      status.value = BrainStatus.idle;
      statusText.value = '';
    }
  }

  void cancel() => _runtime.cancel();

  // ── deciding ────────────────────────────────────────────────────────
  /// Decide what to do with [text]. [commit]: keep the exchange as context for
  /// the next turn (follow-ups, the answer to an `ask`). Shadow runs don't.
  Future<BrainDecision?> decide(String text,
      {required Lang lang, List<Memory> memories = const [], DateTime? now, bool commit = true}) async {
    final prev = _lock;
    final done = Completer<void>();
    _lock = done.future;
    await prev;
    try {
      if (!await ensureReady(lang)) return null;
      if (DateTime.now().difference(_lastTurn) > historyTtl) _history.clear();
      final stopwatch = Stopwatch()..start();
      final rememberedFacts = [for (final memory in memoriesForPrompt(text, memories)) memory.text];
      final system = systemPrompt(tools.values.toList(),
          lang: langRule(lang), now: nowText(now ?? DateTime.now()), memory: rememberedFacts);
      final turns = [..._history, (role: 'user', content: text)];
      final generation = await _runtime.complete(qwenPrompt(system, turns),
          grammar: grammar(), maxTokens: 256, stop: const [imEnd]);
      final contract = parseOutput(generation.text);
      // Names, numbers and message text must come from what the user actually
      // said (this turn or the recent ones a follow-up refers to) — a
      // hallucinated contact never acts.
      final userWords = [for (final turn in turns) if (turn.role == 'user') turn.content].join(' \n ');
      final errors = contract == null
          ? ['not JSON']
          : validate(contract, tools, userText: userWords, grounded: true);
      final decision = BrainDecision(text, generation.text.trim(), contract, errors, generation, stopwatch.elapsedMilliseconds);
      if (commit) _remember(text, contract == null ? generation.text.trim() : canonical(contract, tools));
      _restartIdleTimer();
      return decision;
    } catch (e) {
      statusText.value = 'Error: $e';
      return null;
    } finally {
      done.complete();
    }
  }

  /// Keeps the last 3 exchanges as context for follow-ups.
  void _remember(String userText, String assistantJson) {
    _history
      ..add((role: 'user', content: userText))
      ..add((role: 'assistant', content: assistantJson));
    while (_history.length > 6) {
      _history.removeAt(0);
    }
    _lastTurn = DateTime.now();
  }

  void resetConversation() => _history.clear();

  /// The brain's last turn was a question — the next utterance is its answer.
  bool get awaitingAnswer =>
      _history.isNotEmpty &&
      _history.last.content.startsWith('{"type":"ask"') &&
      DateTime.now().difference(_lastTurn) < historyTtl;

  // ── log: the learning loop's raw material ───────────────────────────
  Future<File> logFile() async => File('${await _supportFolder()}/brain_log.jsonl');

  Future<String> _supportFolder() async => supportDirOverride ?? (await getApplicationSupportDirectory()).path;

  /// Appends one decision to brain_log.jsonl (rotated at 4 MB).
  Future<void> log(BrainDecision decision, {required String mode, String? router, String? outcome}) async {
    try {
      final file = await logFile();
      if (await file.exists() && await file.length() > 4 * 1024 * 1024) await file.rename('${file.path}.1');
      await file.writeAsString(
          '${jsonEncode({
                'at': DateTime.now().toIso8601String(),
                'mode': mode,
                'text': decision.text,
                'raw': decision.raw,
                'valid': decision.valid,
                'errors': decision.errors,
                'summary': decision.summary,
                'router': ?router,
                'outcome': ?outcome,
                'ms': decision.totalMs,
                'ttft_ms': decision.gen?.firstTokenMs,
                'tok_s': decision.gen?.tokPerSec,
              })}\n',
          mode: FileMode.append);
    } catch (_) {}
  }

  /// The last [n] log entries, newest first (Brain screen).
  Future<List<Map<String, dynamic>>> recentLog([int n = 30]) async {
    try {
      final file = await logFile();
      if (!await file.exists()) return const [];
      final lines = (await file.readAsLines()).where((line) => line.trim().isNotEmpty).toList();
      return [
        for (final line in lines.reversed.take(n)) (jsonDecode(line) as Map).cast<String, dynamic>()
      ];
    } catch (_) {
      return const [];
    }
  }
}
