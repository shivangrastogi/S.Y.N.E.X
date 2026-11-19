// Pre-makes "<Name> ka call." for the people who actually call, so their
// whole announcement is ready before the phone rings (the question
// "Uthaun ya kaatun?" is pre-made already — see commonReplies).
//
// Who: starred contacts first, then whoever called in the last 90 days, most
// calls first (android/.../calls/CallerLookup.kt → likelyCallers).
// How much: the top [onBattery] names normally, up to [whileCharging] while
// the phone charges. Anyone else is stored after their first call anyway.
// Manners: one name at a time, and it waits while the user talks to AERIS or
// a call is being handled, so live speech never queues behind it.
import 'dart:async';

import 'package:flutter/foundation.dart';

import '../core/models.dart';
import '../core/store.dart';
import '../voice/io.dart';
import 'call_bridge.dart';
import 'call_phrases.dart';

class CallerVoicePrep {
  CallerVoicePrep({
    required this.store,
    required this.mouth,
    required this.bridge,
    required this.isCharging,
    required this.isBusy,
    this.onBattery = 10,
    this.whileCharging = 40,
    this.busyRecheck = const Duration(seconds: 5),
  });

  final Store store;
  final Mouth mouth;
  final CallBridge bridge;

  /// Whether the phone is charging right now.
  final Future<bool> Function() isCharging;

  /// True while AERIS is talking with the user or handling a call.
  final bool Function() isBusy;

  final int onBattery;
  final int whileCharging;
  final Duration busyRecheck;

  bool _running = false;

  /// Make the announcements that aren't stored yet. Safe to call often
  /// (startup, speed change, charger plugged in): cached ones are skipped,
  /// and a second call while one is running does nothing.
  Future<int> run() async {
    if (_running || !store.settings.callsByVoice) return 0;
    _running = true;
    var made = 0;
    try {
      final limit = await isCharging() ? whileCharging : onBattery;
      final names = await bridge.likelyCallers(limit: limit);
      final phrases = CallPhrases(store.settings.lang == Lang.hinglish);
      for (final name in names) {
        while (isBusy()) {
          await Future<void>.delayed(busyRecheck); // live speech first
        }
        // the same voice, speed and language a real call will use
        await mouth.configure(language: _ttsLanguage, rate: store.settings.rate);
        made += await mouth.prepare([phrases.announce(name)]);
      }
      debugPrint('AERIS caller voices: $made new of ${names.length} likely callers ready');
    } catch (error) {
      debugPrint('AERIS caller voices failed: $error');
    } finally {
      _running = false;
    }
    return made;
  }

  String get _ttsLanguage => switch (store.settings.lang) {
        Lang.hinglish => 'hi-IN',
        Lang.englishIn => 'en-IN',
        Lang.englishUs => 'en-US',
      };
}
