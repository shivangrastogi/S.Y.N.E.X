import 'dart:async';

import 'package:flutter/foundation.dart';

import '../core/models.dart';
import '../core/store.dart';
import 'io.dart';
import 'local/local_mouth.dart';

/// Keeps AERIS's one voice in step with the one speed setting.
///
/// Every place that speaks (conversation, calls, the speed preview) reads
/// `settings.rate` at the moment it speaks, so a new speed applies everywhere
/// at once. The only thing that can lag is the voice cache: pre-made phrases
/// are stored per speed. So when the speed changes, the common replies (call
/// phrases included) are re-made at the new speed in the background — they
/// stay instant instead of being made on first use.
class VoiceSpeedSync {
  VoiceSpeedSync({
    required this.store,
    required this.mouth,
    this.settleDelay = const Duration(seconds: 2),
    this.afterPremake,
  });

  final Store store;
  final Mouth mouth;

  /// More phrases to make at the same speed once the common replies are done
  /// (the likely callers' announcements — calls/caller_voice_prep.dart).
  final Future<void> Function()? afterPremake;

  /// The slider fires many changes while dragging; re-make once it settles.
  final Duration settleDelay;

  double? _preparedRate;
  Timer? _settle;
  bool _preparing = false;

  /// Make the phrases for the current speed now, then follow future changes.
  Future<void> start() async {
    store.addListener(_onSettingsChanged);
    await premake();
  }

  void _onSettingsChanged() {
    if (store.settings.rate == _preparedRate) return;
    _settle?.cancel();
    _settle = Timer(settleDelay, premake);
  }

  /// Pre-make the common replies at the current speed (skips what's cached).
  Future<void> premake() async {
    if (_preparing) return;
    final settings = store.settings;
    _preparing = true;
    try {
      final rate = settings.rate;
      if (settings.lang == Lang.hinglish) {
        // the common replies are Hinglish lines
        await mouth.configure(language: 'hi-IN', rate: rate);
        final made = await mouth.prepare(commonReplies(settings.name.trim()));
        debugPrint('AERIS voice cache: $made new phrases made at ${LocalMouth.speedFor(rate)}×');
      }
      _preparedRate = rate;
    } finally {
      _preparing = false;
    }
    await afterPremake?.call();
    if (store.settings.rate != _preparedRate) _onSettingsChanged(); // changed again meanwhile
  }

  void dispose() {
    _settle?.cancel();
    store.removeListener(_onSettingsChanged);
  }
}
