import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart';

import '../brain/executor.dart';
import '../brain/phone.dart' show pickPerson;
import '../brain/llm/brain.dart';
import '../brain/llm/bridge.dart';
import '../brain/router.dart';
import '../core/models.dart';
import '../core/store.dart';
import '../ui/reactor/reactor.dart';
import 'io.dart';

enum Phase { idle, listening, processing, speaking, approval, noSignal, error }

/// One line in the on-screen exchange.
class Line {
  const Line(this.fromUser, this.text, {this.detail, this.failed = false});
  final bool fromUser;
  final String text;
  final String? detail;
  final bool failed;
}

/// The voice conversation state machine (BUILD_GUIDE §7.6).
///
/// listening → processing → speaking → (keep listening | done)
///                       ↘ approval (haan/nahi or tap) ↗
///
/// Audio-reactive data for the core is exposed as notifiers, never through
/// notifyListeners, so the screen doesn't rebuild 15×/s (aeris_remote ANR).
class VoiceSession extends ChangeNotifier {
  VoiceSession({
    required this.store,
    required this.ears,
    required this.mouth,
    required this.exec,
    this.router = const Router(),
    this.brain,
  });

  final Store store;
  final Ears ears;
  final Mouth mouth;
  final Executor exec;

  /// Instant, rule-based understanding (always asked first).
  final Router router;

  /// On-device LLM for whatever the rules can't handle. Null = rules only.
  final AerisBrain? brain;

  // ── observable state ──
  Phase phase = Phase.idle;
  bool active = false; // overlay visible
  String partial = '';
  String reply = '';
  String? replyDetail;
  String? error;

  /// One-off status while something slow happens (first-run model setup).
  String? notice;
  Approval? approval;
  final List<Line> lines = [];

  /// Live mic level 0..1 (listening).
  final level = ValueNotifier<double>(0);

  /// Fires once per spoken word → ripples on the core.
  final beat = _Beat();

  /// Character range of the word being spoken in [reply].
  final spokenRange = ValueNotifier<(int, int)?>(null);

  // ── internals ──
  Plan? _pending; // awaiting approval
  String _pendingSaid = '';
  String _template = ''; // clarify follow-up: the answer replaces {} (Executor.clarifyTemplate)
  NeedsChoice? _choice; // "Kaunse Rahul?" — the next answer picks one
  bool _typed = false;
  int _silences = 0;
  int _turnId = 0; // bumps on every new turn and on stop(); async work from an older turn checks it and bails

  CoreState get coreState => switch (phase) {
        Phase.idle => CoreState.idle,
        Phase.listening => CoreState.listening,
        Phase.processing => CoreState.processing,
        Phase.speaking => CoreState.speaking,
        Phase.approval => CoreState.approval,
        Phase.noSignal => CoreState.idle,
        Phase.error => CoreState.error,
      };

  bool get _hi => store.settings.lang == Lang.hinglish;
  String get _sttLocale => store.settings.lang == Lang.englishUs ? 'en_US' : 'en_IN';
  String get _ttsLang => switch (store.settings.lang) {
        Lang.hinglish => 'hi-IN', // JARVIS voice speaks Hinglish from Devanagari
        Lang.englishIn => 'en-IN',
        Lang.englishUs => 'en-US',
      };

  void _set(Phase p) {
    phase = p;
    notifyListeners();
  }

  /// Open the overlay and listen.
  Future<void> start() async {
    _turnId++;
    active = true;
    _typed = false;
    _silences = 0;
    lines.clear();
    reply = '';
    replyDetail = null;
    approval = null;
    _pending = null;
    _template = '';
    _choice = null;
    HapticFeedback.lightImpact();
    await _listen();
  }

  /// A typed command: same pipeline, no auto re-listen.
  Future<void> submitText(String text) async {
    if (text.trim().isEmpty) return;
    _turnId++;
    active = true;
    _typed = true;
    lines.clear();
    approval = null;
    _pending = null;
    _choice = null;
    await _handle(text.trim());
  }

  Future<void> _listen() async {
    final turnId = _turnId;
    error = null;
    partial = '';
    if (!ears.available) {
      notice = _hi ? 'AERIS ke kaan tayyar ho rahe hain…' : 'Getting AERIS ready to listen…';
      _set(Phase.processing);
    }
    final ready = await ears.init();
    notice = null;
    if (!ready) {
      error = _hi
          ? 'Mic ya speech recognition available nahi hai. Settings mein mic permission check karein.'
          : 'Speech recognition isn\'t available. Check the microphone permission in Settings.';
      _set(Phase.error);
      return;
    }
    if (turnId != _turnId) return;
    _set(Phase.listening);
    await ears.listen(
      locale: _sttLocale,
      onPartial: (p) {
        if (turnId != _turnId) return;
        partial = p;
        notifyListeners();
      },
      onLevel: (v) => level.value = v,
      onFinal: (text) {
        if (turnId != _turnId) return;
        level.value = 0;
        _silences = 0;
        _handle(text);
      },
      onSilence: () {
        if (turnId != _turnId) return;
        level.value = 0;
        _onSilence();
      },
      onError: (e) {
        if (turnId != _turnId) return;
        level.value = 0;
        error = e;
        _set(Phase.error);
      },
      onTranscribing: () {
        if (turnId != _turnId) return;
        level.value = 0;
        _set(Phase.processing);
      },
    );
  }

  void _onSilence() {
    _silences++;
    // In a running conversation, one quiet turn ends it gracefully.
    if (lines.isNotEmpty || _silences >= 2) {
      if (_pending != null) {
        _resolveApproval(false);
        return;
      }
      stop();
      return;
    }
    _set(Phase.noSignal);
  }

  Future<void> retry() => _listen();

  /// One utterance → one turn. Never leaves the screen stuck on "processing":
  /// anything unexpected becomes a spoken apology and an error state.
  Future<void> _handle(String raw) async {
    final turnId = _turnId;
    try {
      await _handleTurn(raw, turnId);
    } catch (e, stack) {
      debugPrint('AERIS turn failed: $e\n$stack');
      if (turnId != _turnId) return;
      notice = null;
      error = _hi ? 'Kuch gadbad ho gayi. Dobara boliye?' : 'Something went wrong. Try again?';
      _set(Phase.error);
    }
  }

  Future<void> _handleTurn(String raw, int turnId) async {
    partial = '';
    lines.add(Line(true, raw));

    // "Kaunse Rahul?" → "Sharma wale" / "pehla"
    final choice = _choice;
    if (choice != null) {
      _choice = null;
      final picked = pickPerson(raw, choice.options);
      if (picked != null) {
        final stopwatch = Stopwatch()..start();
        final resolved = choice.plan.withArgs({'name': picked.name, 'number': picked.number});
        return _carryOut(raw, resolved, turnId, stopwatch);
      }
      if (yesNo(raw) == YesNo.no) {
        return _respond(Outcome(_hi ? 'Theek hai, rehne dete hain.' : 'Okay, never mind.', status: TurnStatus.cancelled), turnId);
      }
      // anything else is a new command
    }

    if (_pending != null) {
      switch (yesNo(raw)) {
        case YesNo.yes:
          return _resolveApproval(true);
        case YesNo.no:
          return _resolveApproval(false);
        case YesNo.neither:
          _pending = null;
          approval = null; // a new command replaces the pending one
      }
    }

    final text = _template.isEmpty ? raw : _template.replaceFirst('{}', raw);
    _template = '';
    _set(Phase.processing);
    final stopwatch = Stopwatch()..start();
    final plan = router.route(text, protocols: store.protocols, memories: store.memories);

    if (_shouldAskBrain(plan)) {
      final handled = await _handleWithBrain(raw, text, routerPlan: plan, turnId: turnId, stopwatch: stopwatch);
      if (handled || turnId != _turnId) return;
    }
    await _carryOut(raw, plan, turnId, stopwatch);
    _shadowBrain(text, plan);
  }

  /// Runs a plan from either the rule router or the brain: ends, clarifying
  /// questions, protocols, approvals (messages, web search) and plain actions.
  Future<void> _carryOut(String raw, Plan plan, int turnId, Stopwatch stopwatch) async {
    if (plan.tool == 'end') {
      final outcome = await exec.run(plan);
      _log(raw, plan, outcome, stopwatch);
      await _say(outcome.reply, turnId);
      if (turnId == _turnId) stop();
      return;
    }

    if (plan.tool == 'clarify') {
      _template = exec.clarifyTemplate(plan);
      final q = exec.clarify(plan);
      await _say(q, turnId);
      if (turnId == _turnId) await _listen();
      return;
    }

    if (plan.tool == 'protocol') {
      final outcome = await _runProtocol(plan, turnId);
      _log(raw, plan, outcome, stopwatch);
      await _respond(outcome, turnId);
      return;
    }

    // Who is "Rahul"? Resolved before acting or asking — and if two people
    // match, ask which one instead of guessing.
    if (plan.tool == 'call' || plan.tool == 'message') {
      try {
        plan = await exec.prepare(plan);
      } on NeedsChoice catch (c) {
        if (turnId != _turnId) return;
        _choice = c;
        await _say(c.question, turnId);
        if (turnId == _turnId) await _listen();
        return;
      } on PrepareFailed catch (e) {
        final outcome = Outcome(e.reply, status: TurnStatus.failed);
        _log(raw, plan, outcome, stopwatch);
        await _respond(outcome, turnId);
        return;
      }
      if (turnId != _turnId) return;
    }

    if (plan.needsApproval) {
      try {
        final ready = await exec.prepare(plan);
        if (turnId != _turnId) return;
        _pending = ready;
        _pendingSaid = raw;
        approval = exec.approval(ready);
        _set(Phase.approval);
        HapticFeedback.mediumImpact();
        await _say(approval!.question, turnId, keepPhase: true);
        if (turnId == _turnId && _pending != null && !_typed) await _listen();
      } on PrepareFailed catch (e) {
        final outcome = Outcome(e.reply, status: TurnStatus.failed);
        _log(raw, plan, outcome, stopwatch);
        await _respond(outcome, turnId);
      }
      return;
    }

    final outcome = await exec.run(plan);
    if (turnId != _turnId) return;
    _log(raw, plan, outcome, stopwatch);
    await _respond(outcome, turnId);
  }

  // ── the on-device brain ───────────────────────────────────────────

  /// The router's "nothing matched → search the web?" fallback.
  static bool _isRouterFallback(Plan plan) => plan.tool == 'search' && plan.args['fallback'] == true;

  /// Ask the brain when the rules have nothing, or when the brain just asked
  /// a question and this is the answer. "bye" always ends, whatever the brain thinks.
  bool _shouldAskBrain(Plan routerPlan) {
    final llm = brain;
    if (llm == null || !llm.enabled || routerPlan.tool == 'end') return false;
    return _isRouterFallback(routerPlan) || llm.awaitingAnswer;
  }

  /// Returns true when the brain handled the turn; false → fall back to the
  /// router's plan (invalid output, no model, or a tool this app can't run).
  Future<bool> _handleWithBrain(String raw, String text,
      {required Plan routerPlan, required int turnId, required Stopwatch stopwatch}) async {
    final llm = brain!;
    notice = _hi ? 'Soch raha hoon…' : 'Thinking…';
    _set(Phase.processing);
    final decision = await llm.decide(text, lang: store.settings.lang, memories: store.memories);
    notice = null;
    if (turnId != _turnId) return true; // the user closed AERIS meanwhile
    if (decision == null || !decision.valid) {
      if (decision != null) unawaited(llm.log(decision, mode: 'on', router: routerPlan.tool, outcome: 'fallback:invalid'));
      return false;
    }

    final action = actionFromContract(decision.obj!, memories: store.memories);
    unawaited(llm.log(decision, mode: 'on', router: routerPlan.tool, outcome: action.runtimeType.toString()));
    switch (action) {
      case BrainSpeaks(:final text, :final expectsAnswer):
        if (text.isEmpty) return false;
        final outcome = Outcome(text);
        _log(raw, Plan('brain', {'type': decision.type}), outcome, stopwatch);
        await _respond(outcome, turnId, forceListen: expectsAnswer);
        return true;
      case BrainRunsPlan(:final plan):
        await _carryOut(raw, plan, turnId, stopwatch);
        return true;
      case BrainCannotDoYet():
        return false;
    }
  }

  /// Shadow mode: after the router acted, let the brain decide silently and
  /// log both — measures it on real commands before it's trusted.
  void _shadowBrain(String text, Plan routerPlan) {
    final llm = brain;
    if (llm == null || llm.mode.value != BrainMode.shadow || !llm.hasModel) return;
    unawaited(llm
        .decide(text, lang: store.settings.lang, memories: store.memories, commit: false)
        .then((decision) {
      if (decision != null) llm.log(decision, mode: 'shadow', router: routerPlan.toString());
    }));
  }

  /// Tap or voice answer to the approval panel.
  Future<void> _resolveApproval(bool yes) async {
    final turnId = _turnId;
    final plan = _pending;
    _pending = null;
    approval = null;
    if (plan == null) return;
    await ears.cancel();
    await mouth.stop(); // a tap while the question is still being read out
    final stopwatch = Stopwatch()..start();
    if (!yes) {
      final outcome = Outcome(
          plan.tool == 'message'
              ? (_hi ? 'Theek hai, nahi bheja.' : 'Okay, not sent.')
              : (_hi ? 'Theek hai, rehne dete hain.' : 'Okay, never mind.'),
          status: TurnStatus.cancelled);
      _log(_pendingSaid, plan, outcome, stopwatch);
      await _respond(outcome, turnId);
      return;
    }
    _set(Phase.processing);
    final outcome = await exec.run(plan);
    _log(_pendingSaid, plan, outcome, stopwatch);
    await _respond(outcome, turnId);
  }

  /// Speak a short sample at the current speed (Settings ▶).
  Future<void> previewVoice() async {
    await mouth.stop();
    await mouth.configure(language: _ttsLang, rate: store.settings.rate);
    await mouth.speak(_hi
        ? 'Namaste! Main AERIS hoon. Kal subah saade chhe baje ka alarm laga diya hai.'
        : 'Hi, I\'m AERIS. Your alarm is set for six thirty tomorrow morning.');
  }

  Future<void> stopPreview() => mouth.stop();

  void approve() => _resolveApproval(true);
  void deny() => _resolveApproval(false);

  Future<Outcome> _runProtocol(Plan plan, int turnId) async {
    final p = store.protocols.firstWhere((x) => x.id == plan.args['id']);
    final done = <String>[];
    var failed = 0;
    for (final cmd in p.actions) {
      if (turnId != _turnId) break;
      final sub = router.route(cmd, memories: store.memories);
      if (sub.needsApproval || sub.tool == 'protocol' || sub.tool == 'clarify' || sub.tool == 'end') {
        failed++;
        continue; // protocols never send messages or ask questions on their own
      }
      final outcome = await exec.run(sub);
      if (outcome.status == TurnStatus.ok) {
        done.add(outcome.reply);
      } else {
        failed++;
      }
    }
    final summary = p.sayAfter.trim().isNotEmpty ? p.sayAfter.trim() : (_hi ? '${p.name} ho gaya.' : '${p.name} done.');
    return Outcome(summary,
        status: failed == 0 ? TurnStatus.ok : TurnStatus.failed,
        detail: done.join('  ·  '));
  }

  /// Shows and speaks [outcome], then listens again if the conversation continues.
  /// [forceListen]: AERIS asked a question, so listen even when
  /// "keep listening" is off.
  Future<void> _respond(Outcome outcome, int turnId, {bool forceListen = false}) async {
    if (turnId != _turnId) return;
    replyDetail = outcome.detail;
    lines.add(Line(false, outcome.reply, detail: outcome.detail, failed: outcome.status == TurnStatus.failed));
    HapticFeedback.selectionClick();
    await _say(outcome.reply, turnId);
    if (turnId != _turnId) return;
    if (_typed || !(store.settings.keepListening || forceListen)) {
      _set(Phase.idle);
      return;
    }
    await _listen();
  }

  Future<void> _say(String text, int turnId, {bool keepPhase = false}) async {
    if (turnId != _turnId) return;
    reply = text;
    spokenRange.value = null;
    if (!keepPhase) _set(Phase.speaking);
    notifyListeners();
    if (!store.settings.speak) {
      // still give the core a moment of "speaking" so the turn reads
      beat.ping();
      await Future.delayed(const Duration(milliseconds: 500));
      return;
    }
    await mouth.configure(language: _ttsLang, rate: store.settings.rate, voice: store.settings.voice);
    if (turnId != _turnId) return;
    await mouth.speak(text, onWord: (s, e) {
      if (turnId != _turnId) return;
      spokenRange.value = (s, e);
      beat.ping();
    });
    spokenRange.value = null;
  }

  void _log(String said, Plan plan, Outcome outcome, Stopwatch stopwatch) {
    store.addActivity(ActivityEntry(
      id: Store.newId(),
      at: DateTime.now(),
      said: said,
      tool: plan.tool,
      args: {
        for (final e in plan.args.entries)
          if (e.value is String || e.value is num || e.value is bool) e.key: e.value,
      },
      reply: outcome.reply,
      status: outcome.status,
      latencyMs: stopwatch.elapsedMilliseconds,
      typed: _typed,
    ));
  }

  /// Close everything.
  Future<void> stop() async {
    _turnId++;
    _pending = null;
    approval = null;
    _template = '';
    _choice = null;
    level.value = 0;
    spokenRange.value = null;
    active = false;
    phase = Phase.idle;
    notifyListeners();
    await ears.cancel();
    await mouth.stop();
  }

  @override
  void dispose() {
    level.dispose();
    spokenRange.dispose();
    beat.dispose();
    super.dispose();
  }
}

class _Beat extends ChangeNotifier {
  void ping() => notifyListeners();
}
