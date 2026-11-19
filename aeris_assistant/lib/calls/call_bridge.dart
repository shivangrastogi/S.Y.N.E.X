// Dart side of the call plumbing. Android side:
// android/app/src/main/kotlin/com/aeris/aeris_assistant/calls/CallBridge.kt
import 'dart:async';

import 'package:flutter/services.dart';

import 'call_voice_rules.dart';

/// What the edge glow shows (mirrors `GlowState` in EdgeGlowOverlay.kt).
enum GlowState { listening, speaking, accepted, declined, off }

/// Something that happened to a phone call.
sealed class CallEvent {
  const CallEvent();
}

/// The phone is ringing. [number] is empty when Android hides it
/// (call-log permission missing, or a private number). [callerName] is the
/// saved contact's name (looked up on the Android side), empty if unknown.
class CallRinging extends CallEvent {
  const CallRinging(this.number, {this.callerName = ''});
  final String number;
  final String callerName;
}

/// The ringing call was picked up (by AERIS or by touch).
class CallAnswered extends CallEvent {
  const CallAnswered();
}

/// The call is over: declined, missed, or hung up.
class CallEnded extends CallEvent {
  const CallEnded();
}

/// Everything AERIS can do about calls. [CallAssistant] only talks to this,
/// so tests use a fake.
abstract class CallBridge {
  Stream<CallEvent> get events;

  Future<void> startWatching();
  Future<void> stopWatching();
  Future<bool> isWatching();

  Future<bool> answer({bool onSpeaker = false});
  Future<bool> reject();
  Future<bool> sendText(String number, String text);

  /// Fade the ringtone down to its lowest step (AERIS is about to speak and
  /// listen). Never to 0 and never on a vibrating / silent phone: volume 0 IS
  /// vibrate mode on Android, so it would change the user's ringer mode.
  Future<void> silenceRinger({Duration fade = Duration.zero});

  /// Bring the ringtone back to the user's volume (and mode, if anything moved it).
  Future<void> restoreRinger({Duration fade = Duration.zero});

  Future<void> glow(GlowState state);

  /// Mic level 0..1 — the glow breathes with your voice.
  Future<void> glowLevel(double level);

  /// Ringer mode, Do Not Disturb and connected earbuds — decides whether and
  /// where AERIS may speak (call_voice_rules.dart).
  Future<AudioSituation> audioSituation();

  /// Starred contacts, then recent callers (most calls first), at most [limit]
  /// — whose announcements are worth pre-making (caller_voice_prep.dart).
  Future<List<String>> likelyCallers({int limit = 40});

  Future<bool> canDrawOverlays();
  Future<void> openOverlaySettings();
}

class AndroidCallBridge implements CallBridge {
  static const _methods = MethodChannel('aeris/calls');
  static const _eventChannel = EventChannel('aeris/calls/events');

  @override
  late final Stream<CallEvent> events = _eventChannel.receiveBroadcastStream().map((raw) {
    final event = (raw as Map).cast<String, Object?>();
    return switch (event['type']) {
      'ringing' => CallRinging('${event['number'] ?? ''}', callerName: '${event['name'] ?? ''}'),
      'answered' => const CallAnswered(),
      _ => const CallEnded(),
    };
  });

  Future<T?> _call<T>(String method, [Map<String, Object?>? args]) async {
    try {
      return await _methods.invokeMethod<T>(method, args);
    } on MissingPluginException {
      return null; // not on Android (tests, desktop)
    } on PlatformException {
      return null;
    }
  }

  @override
  Future<void> startWatching() => _call<bool>('startWatching');
  @override
  Future<void> stopWatching() => _call<bool>('stopWatching');
  @override
  Future<bool> isWatching() async => await _call<bool>('isWatching') ?? false;
  @override
  Future<bool> answer({bool onSpeaker = false}) async => await _call<bool>('answer', {'speaker': onSpeaker}) ?? false;
  @override
  Future<bool> reject() async => await _call<bool>('reject') ?? false;
  @override
  Future<bool> sendText(String number, String text) async =>
      await _call<bool>('sendText', {'number': number, 'text': text}) ?? false;
  @override
  Future<void> silenceRinger({Duration fade = Duration.zero}) =>
      _call<void>('silenceRinger', {'fadeMs': fade.inMilliseconds});
  @override
  Future<void> restoreRinger({Duration fade = Duration.zero}) =>
      _call<void>('restoreRinger', {'fadeMs': fade.inMilliseconds});
  @override
  Future<void> glow(GlowState state) => _call<void>('glow', {'state': state.name});
  @override
  Future<void> glowLevel(double level) => _call<void>('glowLevel', {'level': level});
  @override
  Future<AudioSituation> audioSituation() async {
    final map = await _call<Map<Object?, Object?>>('audioSituation');
    return map == null ? const AudioSituation() : AudioSituation.fromMap(map.cast<String, Object?>());
  }

  @override
  Future<List<String>> likelyCallers({int limit = 40}) async =>
      (await _call<List<Object?>>('likelyCallers', {'limit': limit}))?.map((name) => '$name').toList() ?? const [];

  @override
  Future<bool> canDrawOverlays() async => await _call<bool>('canDrawOverlays') ?? false;
  @override
  Future<void> openOverlaySettings() => _call<void>('openOverlaySettings');
}
