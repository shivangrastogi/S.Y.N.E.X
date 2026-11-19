// Incoming calls, by voice. No screen — only the edge glow:
//
//   ringing  → the phone rings normally for ~2 rings while AERIS prepares its
//              sentence in the background (so it plays in one smooth go)
//            → the ringtone fades down to silent
//            → "Ravi Sharma ka call. Uthaun ya kaatun?" → listen (still silent)
//     "uthao"            → answer            (glow flashes mint)
//     "speaker pe uthao" → answer on speaker
//     "kaat do"          → decline           (glow flashes red)
//         saved contact → "Ravi ko message bhejun ki baad mein baat karte hain?"
//             "haan" → SMS sent directly, no screen
//     unclear twice      → the ringtone fades back up; the phone rings normally
//   The user can always use the phone's own Accept / Reject buttons — AERIS
//   notices (CallAnswered / CallEnded) and steps back immediately.
import 'dart:async';

import 'package:flutter/foundation.dart';

import '../brain/phone.dart';
import '../brain/router.dart' show YesNo, yesNo;
import '../core/models.dart';
import '../core/store.dart';
import '../voice/io.dart';
import '../voice/session.dart';
import 'call_bridge.dart';
import 'call_commands.dart';
import 'call_phrases.dart';
import 'call_voice_rules.dart';

/// Where the call flow is. [CallFlowPhase.idle] = nothing to do.
enum CallFlowPhase { idle, announcing, listening, followUp }

class CallAssistant extends ChangeNotifier {
  CallAssistant({
    required this.store,
    required this.ears,
    required this.mouth,
    required this.phone,
    required this.bridge,
    required this.session,
    this.listenAttempts = 2,
    this.outcomeHold = const Duration(milliseconds: 900),
    this.ringBeforeSpeaking = const Duration(seconds: 4),
    this.ringerFadeDown = const Duration(milliseconds: 800),
    this.ringerFadeUp = const Duration(milliseconds: 1500),
    this.maxPrepareWait = const Duration(seconds: 9),
  });

  final Store store;
  final Ears ears;
  final Mouth mouth;
  final Phone phone;
  final CallBridge bridge;

  /// The normal voice conversation — stopped when a call comes in.
  final VoiceSession session;

  /// How many times AERIS listens for an answer before letting it ring.
  final int listenAttempts;

  /// How long the mint / red outcome glow stays before fading (tests: zero).
  final Duration outcomeHold;

  /// The phone rings normally this long (~2 rings) before AERIS speaks, so a
  /// call still feels like a call — and the sentence is made meanwhile.
  final Duration ringBeforeSpeaking;

  /// How fast the ringtone fades out before AERIS speaks, and back in when
  /// nobody answered by voice.
  final Duration ringerFadeDown;
  final Duration ringerFadeUp;

  /// Never wait longer than this for the sentence to be made (a busy phone).
  final Duration maxPrepareWait;

  CallFlowPhase phase = CallFlowPhase.idle;
  StreamSubscription<CallEvent>? _subscription;

  /// Bumped for every new call and whenever the user takes over by touch;
  /// async steps from an older value stop.
  int _callId = 0;

  /// Set when AERIS itself answered / declined, so the resulting
  /// CallAnswered / CallEnded event doesn't cancel the follow-up.
  bool _actedByVoice = false;

  /// True during [rehearse]: nothing real is answered, declined or sent.
  bool _rehearsal = false;

  /// One logcat line per step (tag AERIS_CALL) — how the flow is checked on a phone.
  void _trace(String step) => debugPrint('AERIS_CALL $step');

  CallPhrases get _phrases => CallPhrases(store.settings.lang == Lang.hinglish);
  String get _ttsLanguage => switch (store.settings.lang) {
        Lang.hinglish => 'hi-IN',
        Lang.englishIn => 'en-IN',
        Lang.englishUs => 'en-US',
      };
  String get _sttLocale => store.settings.lang == Lang.englishUs ? 'en_US' : 'en_IN';

  /// Start reacting to call events (once, at app start).
  void attach() => _subscription ??= bridge.events.listen(_onCallEvent);

  /// Start / stop the background watcher to match the setting.
  Future<void> applySetting() =>
      store.settings.callsByVoice ? bridge.startWatching() : bridge.stopWatching();

  void _onCallEvent(CallEvent event) {
    switch (event) {
      case CallRinging(:final number, :final callerName):
        if (store.settings.callsByVoice) unawaited(handleIncomingCall(number, callerName: callerName));
      case CallAnswered() || CallEnded():
        if (_actedByVoice) return; // our own answer / decline
        if (phase == CallFlowPhase.announcing || phase == CallFlowPhase.listening) {
          unawaited(_stepBack()); // picked up / declined by touch, or the caller hung up
        }
    }
  }

  /// A practice run of the whole flow — glow, announcement, listening — that
  /// never touches a real call, the ringer, or SMS. Settings → Calls →
  /// "Rehearse a call", and `adb ... --es route /calltest` for testing.
  Future<void> rehearse({String number = '', String callerName = ''}) =>
      handleIncomingCall(number, callerName: callerName, rehearsal: true);

  /// The whole flow for one ringing call. Never throws, and always ends idle
  /// with the glow off and the ringer restored — so the next call works even
  /// if something in this one failed.
  @visibleForTesting
  Future<void> handleIncomingCall(String number, {String callerName = '', bool rehearsal = false}) async {
    if (phase != CallFlowPhase.idle) {
      _trace('ringing ignored: still busy with the previous call (${phase.name})');
      return;
    }
    final callId = ++_callId;
    _actedByVoice = false;
    _rehearsal = rehearsal;
    _trace('ringing: ${number.isEmpty ? 'hidden number' : 'number known'}, '
        '${callerName.isEmpty ? 'not in contacts' : 'saved contact'}${rehearsal ? ' (rehearsal)' : ''}');
    try {
      await _runCallFlow(callId, number, callerName.isEmpty ? null : Person(callerName, number));
    } catch (error, stack) {
      _trace('FAILED: $error');
      debugPrintStack(stackTrace: stack, maxFrames: 8);
      if (!_rehearsal) await bridge.restoreRinger();
      await _finish(GlowState.off);
    }
  }

  Future<void> _runCallFlow(int callId, String number, Person? caller) async {
    bool stillCurrent() => callId == _callId;
    // 0. Obey the phone: silent stays silent unless earbuds are in (call_voice_rules.dart).
    final phone = await bridge.audioSituation();
    final voice = voiceForRingingCall(phone);
    _trace('phone: ${phone.describe()} → ${voice?.name ?? 'stay quiet'}');
    if (voice == null) return; // no sound, no glow — the phone rings / vibrates as usual

    if (session.active) await session.stop(); // a call beats a chat
    final phrases = _phrases;

    _setPhase(CallFlowPhase.announcing);
    // the same voice at the same speed as everywhere else (Settings → speed)
    await mouth.configure(language: _ttsLanguage, rate: store.settings.rate, output: voice);

    // 1. Let it ring while the sentence is made (making it while playing is
    //    what made the voice stutter over the ringtone).
    final announcement = phrases.announce(caller?.name);
    final clock = Stopwatch()..start();
    await Future.wait([
      mouth.prepare([announcement, phrases.question()]).timeout(maxPrepareWait, onTimeout: () => 0),
      Future<void>.delayed(ringBeforeSpeaking),
    ]);
    _trace('voice ready after ${clock.elapsedMilliseconds} ms of ringing');
    if (!stillCurrent()) return;

    // 2. Glow on, ringtone down, then speak. (Picked up / declined by touch
    //    during the first rings → AERIS never showed or said anything.)
    await bridge.glow(GlowState.speaking);
    if (!_rehearsal) {
      await bridge.silenceRinger(fade: ringerFadeDown);
      await Future<void>.delayed(ringerFadeDown);
    }
    if (!stillCurrent()) return;
    _trace('announcing');
    if (!await mouth.speak(announcement)) {
      if (!stillCurrent()) return; // stopped because the user took over by touch
      _trace('the voice could not reach the earbuds → staying quiet, ringtone back');
      if (!_rehearsal) await bridge.restoreRinger(fade: ringerFadeUp);
      await _finish(GlowState.off);
      return;
    }

    CallChoice? choice;
    for (var attempt = 0; attempt < listenAttempts && stillCurrent(); attempt++) {
      if (attempt > 0) {
        await bridge.glow(GlowState.speaking);
        await mouth.speak(phrases.question());
      }
      if (!stillCurrent()) break;
      _setPhase(CallFlowPhase.listening);
      await bridge.glow(GlowState.listening);
      final heard = await _listenOnce();
      choice = callChoiceFrom(heard ?? '');
      _trace('attempt ${attempt + 1}: heard "${heard ?? '(silence)'}" → ${choice?.name ?? 'unclear'}');
      if (choice != null) break;
    }
    if (!stillCurrent()) return;

    // 3. Act. The ringtone comes back at once after answering / declining
    //    (the call is over or connected), or fades back in if nobody answered.
    if (!_rehearsal) await bridge.restoreRinger(fade: choice == null ? ringerFadeUp : Duration.zero);
    switch (choice) {
      case CallChoice.answer || CallChoice.answerOnSpeaker:
        _actedByVoice = true;
        final answered = _rehearsal || await bridge.answer(onSpeaker: choice == CallChoice.answerOnSpeaker);
        _trace('answer → ${answered ? 'ok' : 'FAILED'}');
        await _finish(answered ? GlowState.accepted : GlowState.off);
      case CallChoice.decline:
        _actedByVoice = true;
        final declined = _rehearsal || await bridge.reject();
        _trace('decline → ${declined ? 'ok' : 'FAILED'}');
        await bridge.glow(declined ? GlowState.declined : GlowState.off);
        if (declined && caller != null) {
          await _offerTextMessage(caller, callId);
        } else {
          await _finish(GlowState.off);
        }
      case null:
        _trace('no clear answer → ringtone back, letting it ring');
        await _finish(GlowState.off); // nothing clear → it just keeps ringing
    }
  }

  /// "Ravi ko message bhejun…?" → on "haan", SMS straight away (no screen).
  Future<void> _offerTextMessage(Person caller, int callId) async {
    final phrases = _phrases;
    _setPhase(CallFlowPhase.followUp);
    await bridge.glow(GlowState.speaking);
    await mouth.speak(phrases.offerText(caller.name.split(' ').first));
    if (callId != _callId) return;
    await bridge.glow(GlowState.listening);
    final reply = await _listenOnce();
    if (callId != _callId) return;
    if (reply != null && yesNo(reply) == YesNo.yes) {
      final sent = _rehearsal || await bridge.sendText(caller.number, phrases.textMessage());
      _trace('text message → ${_rehearsal ? 'skipped (rehearsal)' : sent ? 'sent' : 'FAILED'}');
      await bridge.glow(sent ? GlowState.accepted : GlowState.declined);
      await mouth.speak(sent ? phrases.textSent() : phrases.textFailed());
    }
    await _finish(GlowState.off);
  }

  /// One listening turn. Returns what was said, or null on silence / error.
  /// The mic level drives the glow.
  Future<String?> _listenOnce() async {
    if (!await ears.init()) return null;
    final heard = Completer<String?>();
    await ears.listen(
      locale: _sttLocale,
      onPartial: (_) {},
      onLevel: (level) => unawaited(bridge.glowLevel(level)),
      onFinal: (text) => heard.isCompleted ? null : heard.complete(text),
      onSilence: () => heard.isCompleted ? null : heard.complete(null),
      onError: (_) => heard.isCompleted ? null : heard.complete(null),
      usePhoneMic: true, // earbuds keep their mic off until a call is picked up
    );
    return heard.future;
  }

  /// The user acted by touch (or the caller hung up): stop talking at once.
  Future<void> _stepBack() async {
    _trace('handled by touch / caller hung up → stepping back');
    _callId++; // invalidates the running flow
    await ears.cancel();
    await mouth.stop();
    await bridge.restoreRinger();
    await _finish(GlowState.off);
  }

  /// Leave the outcome colour on briefly, then fade the glow away.
  Future<void> _finish(GlowState lastGlow) async {
    if (lastGlow == GlowState.accepted || lastGlow == GlowState.declined) {
      await bridge.glow(lastGlow);
      await Future<void>.delayed(outcomeHold);
    }
    await bridge.glow(GlowState.off);
    _setPhase(CallFlowPhase.idle);
    _trace('done');
  }

  void _setPhase(CallFlowPhase newPhase) {
    phase = newPhase;
    notifyListeners();
  }

  @override
  void dispose() {
    _subscription?.cancel();
    super.dispose();
  }
}
