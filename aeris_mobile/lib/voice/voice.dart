/// Voice in and out, behind interfaces.
///
/// The plugins that back these are Android/iOS-first: `speech_to_text` has no
/// Windows implementation at all, and both throw `MissingPluginException` where
/// they are absent. Rather than let that reach the UI, every implementation
/// reports [isAvailable], and the shell hides the microphone when it is false.
/// That also lets the whole app run headless in tests with no plugin channel.
library;

import 'dart:async';

/// What the microphone is doing, for the UI to render.
enum MicState {
  /// No speech plugin on this platform, or permission was refused.
  unavailable,

  /// Ready, not currently listening.
  idle,

  /// Capturing speech now.
  listening,
}

typedef TranscriptCallback = void Function(String text, bool isFinal);

abstract class VoiceIn {
  /// Prepares the recogniser and asks for microphone permission.
  /// Returns whether listening is possible from here on.
  Future<bool> init();

  bool get isAvailable;
  bool get isListening;

  /// Starts capturing. [onText] fires repeatedly with partial transcripts and
  /// once with `isFinal: true`. Call [stop] to end early.
  Future<void> start(TranscriptCallback onText);

  Future<void> stop();

  void dispose();
}

abstract class VoiceOut {
  Future<bool> init();

  bool get isAvailable;

  Future<void> speak(String text);

  /// Cuts off mid-sentence — used when the user sends a new turn.
  Future<void> stop();

  void dispose();
}

/// Strips what a speech engine cannot pronounce, keeping Latin and Devanagari
/// so Hinglish replies survive intact.
///
/// Without this, a reply containing an emoji or a box-drawing character makes
/// the engine either spell it out or fall silent.
String speakable(String text) {
  final cleaned = text
      .replaceAll(RegExp(r'[^\x20-\x7Eऀ-ॿ]'), ' ')
      .replaceAll(RegExp(r'\s+'), ' ')
      .trim();
  return cleaned;
}

/// Used on platforms with no speech plugin, and in tests. Every call is a
/// no-op, and [isAvailable] is false so the UI never offers the microphone.
class SilentVoiceIn implements VoiceIn {
  @override
  bool get isAvailable => false;

  @override
  bool get isListening => false;

  @override
  Future<bool> init() async => false;

  @override
  Future<void> start(TranscriptCallback onText) async {}

  @override
  Future<void> stop() async {}

  @override
  void dispose() {}
}

class SilentVoiceOut implements VoiceOut {
  @override
  bool get isAvailable => false;

  @override
  Future<bool> init() async => false;

  @override
  Future<void> speak(String text) async {}

  @override
  Future<void> stop() async {}

  @override
  void dispose() {}
}
