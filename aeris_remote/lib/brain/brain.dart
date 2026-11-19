// AERIS's on-device brain: a fine-tuned small LLM (Qwen3 1.7B, GGUF) that
// turns what you said into ONE contract object — act / ask / reply / plan /
// escalate (docs/AERIS_MOBILE_BRAIN_PLAN.md §3).
//
// Modes (Assistant settings → Brain):
//   off     the rule-based skills + cloud handle everything (as before)
//   shadow  the old path acts; the brain decides silently alongside and both
//           are logged, so its accuracy is measured on YOUR real commands
//           before it is trusted with anything (plan §3, decision 5)
//   on      the brain decides first; anything invalid, ungrounded or
//           unsure falls back to the old path
//
// The model file lives in the app's external files dir (no permission
// needed; `adb push x.gguf /sdcard/Android/data/com.aeris.aeris_remote/
// files/models/`) or is picked in the Brain screen.
import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart' show rootBundle;
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:path_provider/path_provider.dart';

import '../core/lang.dart';
import 'contract.dart';
import 'grammar.dart';
import 'prompt.dart';
import 'runtime.dart';

enum BrainMode { off, shadow, on }

enum BrainStatus { noModel, idle, loading, ready, error }

class BrainDecision {
  final String text; // what the user said
  final String raw; // model output
  final Map<String, dynamic>? obj;
  final List<String> errors;
  final BrainGeneration? gen;
  final int totalMs;
  const BrainDecision(this.text, this.raw, this.obj, this.errors, this.gen, this.totalMs);

  bool get valid => obj != null && errors.isEmpty;
  String? get type => obj?['type'] as String?;
  List<Map<String, dynamic>> get calls => [
        for (final c in (obj?['calls'] as List? ?? const []))
          (c as Map).cast<String, dynamic>()
      ];

  /// One line for logs and the Brain screen.
  String get summary {
    if (!valid) return 'invalid: ${errors.isEmpty ? raw : errors.join('; ')}';
    return switch (type) {
      'tool_call' => calls.map((c) => '${c['name']}(${jsonEncode(c['args'])})').join(' + '),
      'ask' => 'ask: ${obj!['text']}',
      'reply' => 'reply: ${obj!['text']}',
      'plan' => 'plan: ${obj!['goal']}',
      _ => 'escalate(${obj!['reason']}): ${obj!['query']}',
    };
  }
}

class AerisBrain {
  AerisBrain({BrainRuntime? runtime, String? toolsJson, String? supportDir})
      : _runtime = runtime ?? LlamaRuntime(),
        _toolsJson = toolsJson,
        _supportDir = supportDir;
  static final AerisBrain instance = AerisBrain();

  final BrainRuntime _runtime;
  final String? _toolsJson;
  final String? _supportDir; // tests: no path_provider plugin
  static const _store = FlutterSecureStorage();
  static const _kMode = 'brain_mode', _kModel = 'brain_model_path', _kThreads = 'brain_threads';
  static const idleUnload = Duration(minutes: 10);
  static const historyTtl = Duration(minutes: 2);

  final ValueNotifier<BrainMode> mode = ValueNotifier(BrainMode.off);
  final ValueNotifier<BrainStatus> status = ValueNotifier(BrainStatus.idle);
  final ValueNotifier<String> statusText = ValueNotifier('');

  Map<String, ToolSpec>? _tools;
  String? _modelPath;
  int threads = 4;
  final List<Turn> _history = [];
  DateTime _lastTurn = DateTime.fromMillisecondsSinceEpoch(0);
  Timer? _idle;
  Future<void> _lock = Future.value();
  bool _busy = false;
  String? _warmFor; // system prompt the KV prefix was built for
  Future<bool>? _loading;

  bool get busy => _busy;
  String? get modelPath => _modelPath;
  Map<String, ToolSpec> get tools => _tools ?? const {};

  // ── settings ────────────────────────────────────────────────────────
  Future<void> load() async {
    try {
      final m = await _store.read(key: _kMode);
      mode.value = BrainMode.values.firstWhere((x) => x.name == m, orElse: () => BrainMode.off);
      _modelPath = await _store.read(key: _kModel);
      threads = int.tryParse(await _store.read(key: _kThreads) ?? '') ?? 4;
    } catch (_) {}
    await _ensureTools();
    _modelPath ??= (await findModels()).firstOrNull?.path;
    status.value = _modelPath == null ? BrainStatus.noModel : BrainStatus.idle;
  }

  Future<void> setMode(BrainMode m) async {
    mode.value = m;
    try {
      await _store.write(key: _kMode, value: m.name);
    } catch (_) {}
    if (m == BrainMode.off) await unload();
  }

  Future<void> setModelPath(String path) async {
    _modelPath = path;
    try {
      await _store.write(key: _kModel, value: path);
    } catch (_) {}
    await unload();
    status.value = BrainStatus.idle;
  }

  Future<void> setThreads(int n) async {
    threads = n;
    try {
      await _store.write(key: _kThreads, value: '$n');
    } catch (_) {}
    await unload();
  }

  /// Where models are looked for (first = the adb-push target).
  static Future<List<Directory>> modelDirs() async => [
        if (await getExternalStorageDirectory() case final ext?) Directory('${ext.path}/models'),
        Directory('${(await getApplicationSupportDirectory()).path}/models'),
      ];

  static Future<List<File>> findModels() async {
    final out = <File>[];
    for (final d in await modelDirs()) {
      if (!await d.exists()) continue;
      await for (final f in d.list()) {
        if (f is File && f.path.toLowerCase().endsWith('.gguf')) out.add(f);
      }
    }
    out.sort((a, b) => b.statSync().modified.compareTo(a.statSync().modified));
    return out;
  }

  Future<void> _ensureTools() async {
    _tools ??= parseTools(_toolsJson ?? await rootBundle.loadString('assets/brain/tools.json'));
  }

  // ── prompt pieces ───────────────────────────────────────────────────
  /// App language → the trained language rule.
  static String langRule() => switch (Lang.mode.value) {
        LangMode.hinglish => 'match',
        _ => 'english',
      };

  /// All tools, registry order, no `now`/memory: a byte-stable prefix, so
  /// its KV cache is computed once and reused for every turn.
  String systemText() => systemPrompt(tools.values.toList(), lang: langRule());

  String? _grammar;
  String grammar() => _grammar ??= contractGrammar(tools.values.toList()).toGbnf();

  // ── lifecycle ───────────────────────────────────────────────────────
  Future<bool> ensureReady() async {
    await _ensureTools();
    if (_runtime.isLoaded && _warmFor == systemText()) {
      _touch();
      return true;
    }
    return _loading ??= _doLoad().whenComplete(() => _loading = null);
  }

  Future<bool> _doLoad() async {
    final path = _modelPath ?? (await findModels()).firstOrNull?.path;
    if (path == null || !await File(path).exists()) {
      status.value = BrainStatus.noModel;
      statusText.value = 'No model file';
      return false;
    }
    _modelPath = path;
    try {
      status.value = BrainStatus.loading;
      final sw = Stopwatch()..start();
      if (!_runtime.isLoaded) {
        statusText.value = 'Loading model…';
        await _runtime.load(path, threads: threads);
      }
      statusText.value = 'Preparing prompt…';
      final sys = systemText();
      final prefix = qwenPrompt(sys, const []).split('<|im_start|>assistant').first;
      final reused = await _runtime.warmPrefix(prefix, await _cacheFile(path, sys));
      _warmFor = sys;
      status.value = BrainStatus.ready;
      statusText.value = 'Ready in ${(sw.elapsedMilliseconds / 1000).toStringAsFixed(1)} s'
          '${reused ? ' (cached prompt)' : ''}';
      _touch();
      return true;
    } catch (e) {
      status.value = BrainStatus.error;
      statusText.value = '$e';
      await _runtime.unload();
      return false;
    }
  }

  Future<String> _cacheFile(String model, String sys) async {
    final st = await File(model).stat();
    final key = _fnv('$model|${st.size}|${st.modified.millisecondsSinceEpoch}|$sys');
    return '${await _support()}/brain_cache/$key.kv';
  }

  static String _fnv(String s) {
    var h = 0xcbf29ce484222325;
    for (final c in utf8.encode(s)) {
      h = (h ^ c) * 0x100000001b3;
    }
    return h.toUnsigned(64).toRadixString(16);
  }

  void _touch() {
    _idle?.cancel();
    _idle = Timer(idleUnload, unload);
  }

  /// Frees the model's ~1.8 GB. Reloading is a few seconds (mmap + cached
  /// prompt state), so idle phones don't carry it.
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
  /// Decide what to do with [text]. [commit]: keep this exchange as context
  /// for the next turn (follow-ups like "aur usko call bhi karo", or the
  /// answer to an `ask`). Shadow runs don't commit.
  Future<BrainDecision?> decide(String text, {bool commit = true}) async {
    final prev = _lock;
    final done = Completer<void>();
    _lock = done.future;
    await prev;
    _busy = true;
    try {
      if (!await ensureReady()) return null;
      if (DateTime.now().difference(_lastTurn) > historyTtl) _history.clear();
      final sw = Stopwatch()..start();
      final turns = [..._history, (role: 'user', content: text)];
      final gen = await _runtime.complete(qwenPrompt(systemText(), turns),
          grammar: grammar(), maxTokens: 256, stop: const [imEnd]);
      final obj = parseOutput(gen.text);
      // Spans must come from what the user actually said (this turn or the
      // recent ones a follow-up refers to) — a hallucinated name never acts.
      final said = [for (final t in turns) if (t.role == 'user') t.content].join(' \n ');
      final errs = obj == null
          ? ['not JSON']
          : validate(obj, tools, userText: said, grounded: true);
      final d = BrainDecision(text, gen.text.trim(), obj, errs, gen, sw.elapsedMilliseconds);
      if (commit) {
        _history
          ..add((role: 'user', content: text))
          ..add((role: 'assistant', content: obj == null ? gen.text.trim() : canonical(obj, tools)));
        while (_history.length > 6) {
          _history.removeAt(0);
        }
        _lastTurn = DateTime.now();
      }
      _touch();
      return d;
    } catch (e) {
      statusText.value = 'Error: $e';
      return null;
    } finally {
      _busy = false;
      done.complete();
    }
  }

  void resetConversation() => _history.clear();

  /// The brain's last turn was a question ("What should I tell Ravi?") —
  /// the next utterance is its answer and must come back here first.
  bool get awaitingAnswer =>
      _history.isNotEmpty &&
      _history.last.content.startsWith('{"type":"ask"') &&
      DateTime.now().difference(_lastTurn) < historyTtl;

  // ── shadow / misses log (the learning loop's raw material, plan §9) ──
  Future<File> logFile() async => File('${await _support()}/brain_log.jsonl');

  Future<String> _support() async =>
      _supportDir ?? (await getApplicationSupportDirectory()).path;

  Future<void> log(BrainDecision d, {required String mode, String? legacy, String? outcome}) async {
    try {
      final f = await logFile();
      if (await f.exists() && await f.length() > 4 * 1024 * 1024) {
        await f.rename('${f.path}.1');
      }
      await f.writeAsString(
          '${jsonEncode({
                'at': DateTime.now().toIso8601String(),
                'mode': mode,
                'lang': langRule(),
                'text': d.text,
                'raw': d.raw,
                'valid': d.valid,
                'errors': d.errors,
                'summary': d.summary,
                if (legacy != null) 'legacy': legacy,
                if (outcome != null) 'outcome': outcome,
                'ms': d.totalMs,
                'ttft_ms': d.gen?.firstTokenMs,
                'tok_s': d.gen?.tokPerSec,
              })}\n',
          mode: FileMode.append);
    } catch (_) {}
  }
}
