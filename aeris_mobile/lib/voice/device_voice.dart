import 'dart:async';

import 'package:flutter_tts/flutter_tts.dart';
import 'package:speech_to_text/speech_to_text.dart';

import '../core/logger.dart';
import 'voice.dart';

/// Speech recognition through the phone's own recogniser.
///
/// Native STT on purpose: it already handles the user's Hinglish, needs no
/// bundled model, and costs nothing. The trade is that it only exists on
/// Android and iOS — everywhere else [isAvailable] stays false.
class DeviceVoiceIn implements VoiceIn {
  DeviceVoiceIn({this.locale = 'en_IN'});

  /// Indian English: matches how the user actually speaks, and keeps STT and
  /// TTS on the same variety.
  final String locale;

  final SpeechToText _stt = SpeechToText();
  bool _ready = false;
  bool _listening = false;
  Timer? _guard;

  @override
  bool get isAvailable => _ready;

  @override
  bool get isListening => _listening;

  @override
  Future<bool> init() async {
    try {
      _ready = await _stt.initialize(
        onStatus: (s) {
          if (s == 'done' || s == 'notListening') _listening = false;
        },
        onError: (e) {
          // A stray no_match on silence is normal, not a failure worth showing.
          log.debug('voice', 'stt: ${e.errorMsg}');
          _listening = false;
        },
      );
    } catch (e) {
      // No plugin on this platform, or the permission dialog was refused.
      log.info('voice', 'speech recognition unavailable: $e');
      _ready = false;
    }
    return _ready;
  }

  @override
  Future<void> start(TranscriptCallback onText) async {
    if (!_ready || _listening) return;
    _listening = true;
    try {
      await _stt.listen(
        listenOptions: SpeechListenOptions(
          partialResults: true, // the transcript fills in as you speak
          localeId: locale,
          listenFor: const Duration(seconds: 20),
          pauseFor: const Duration(seconds: 3),
        ),
        onResult: (r) {
          onText(r.recognizedWords.trim(), r.finalResult);
          if (r.finalResult) _listening = false;
        },
      );

      // Backstop: if the engine neither errors nor completes, don't strand the
      // UI in a listening state for ever.
      _guard?.cancel();
      _guard = Timer(const Duration(seconds: 25), () {
        if (_listening) {
          log.warn('voice', 'listen timed out, forcing stop');
          stop();
        }
      });
    } catch (e) {
      log.error('voice', 'listen failed: $e');
      _listening = false;
    }
  }

  @override
  Future<void> stop() async {
    _guard?.cancel();
    _listening = false;
    try {
      await _stt.stop();
    } catch (_) {
      // Already stopped, or the channel is gone. Nothing to recover.
    }
  }

  @override
  void dispose() {
    _guard?.cancel();
    _stt.cancel();
  }
}

/// Speech synthesis through the phone's TTS engine.
class DeviceVoiceOut implements VoiceOut {
  DeviceVoiceOut({this.language = 'en-IN', this.rate = 0.5, this.pitch = 1.0});

  final String language;

  /// 0.5 reads at a natural pace on Android; the platform default gabbles.
  final double rate;
  final double pitch;

  final FlutterTts _tts = FlutterTts();
  bool _ready = false;

  @override
  bool get isAvailable => _ready;

  @override
  Future<bool> init() async {
    try {
      await _tts.setLanguage(language);
      await _tts.setSpeechRate(rate);
      await _tts.setPitch(pitch);
      // So `speak` resolves when the sentence finishes rather than when it
      // starts — the caller needs to know when the mic is safe to reopen.
      await _tts.awaitSpeakCompletion(true);
      _ready = true;
    } catch (e) {
      log.info('voice', 'speech synthesis unavailable: $e');
      _ready = false;
    }
    return _ready;
  }

  @override
  Future<void> speak(String text) async {
    if (!_ready) return;
    final clean = speakable(text);
    if (clean.isEmpty) return;
    try {
      await _tts.stop(); // never let two replies overlap
      await _tts.speak(clean);
    } catch (e) {
      log.error('voice', 'speak failed: $e');
    }
  }

  @override
  Future<void> stop() async {
    try {
      await _tts.stop();
    } catch (_) {
      // Nothing was speaking.
    }
  }

  @override
  void dispose() {
    _tts.stop();
  }
}
