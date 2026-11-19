import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:speech_to_text/speech_recognition_error.dart';
import 'package:speech_to_text/speech_recognition_result.dart';
import 'package:speech_to_text/speech_to_text.dart';

/// Speech in. Real impl = Android SpeechRecognizer (Google, en-IN).
abstract class Ears {
  Future<bool> init();
  bool get available;

  /// Starts one listening turn. Exactly one of [onFinal] / [onSilence] /
  /// [onError] fires per turn.
  ///
  /// [usePhoneMic]: record with the phone's own microphone even when
  /// Bluetooth earbuds are connected. While a call is still ringing, earbuds
  /// keep their mic off until the call is picked up, so listening through
  /// them hears nothing (found on the phone, 2026-11-17).
  Future<void> listen({
    required String locale,
    required void Function(String partial) onPartial,
    required void Function(String text) onFinal,
    required void Function() onSilence,
    required void Function(String error) onError,
    required void Function(double level) onLevel,
    void Function()? onTranscribing,
    bool usePhoneMic = false,
  });
  Future<void> stop();
  Future<void> cancel();
}

/// How AERIS's voice is played.
enum SpeechOutput {
  /// Normal conversation: plays as media and politely takes audio focus
  /// (other apps' music pauses while AERIS talks).
  normal,

  /// While the phone rings, out loud. Android refuses audio focus to every
  /// app during a ringing call (a player that waits for it stays silent), so
  /// this plays on the alarm channel without asking.
  ringingAloud,

  /// While the phone rings, into the earbuds ONLY — never the phone speaker
  /// (a silent phone stays silent). If Android won't route it to the earbuds,
  /// nothing is played and [Mouth.speak] returns false.
  ringingEarbudsOnly,
}

/// Speech out. [onWord] fires as each word starts (drives word-sync + ripples).
abstract class Mouth {
  Future<void> configure({
    required String language,
    required double rate,
    String? voice,
    SpeechOutput output = SpeechOutput.normal,
  });
  /// Returns false when the speech could not be played where it was meant to
  /// go (e.g. earbuds-only and Android routed it elsewhere) — nobody heard it.
  Future<bool> speak(String text, {void Function(int start, int end)? onWord});

  /// Make [texts] ahead of time without playing them, so a later [speak]
  /// starts at once and flows without gaps. Returns how many were new.
  Future<int> prepare(Iterable<String> texts);
  Future<void> stop();
  String get engineName;
}

class DeviceEars implements Ears {
  final _stt = SpeechToText();
  bool _ok = false;
  int _turn = 0;
  bool _settled = true;
  String _best = '';
  void Function(String)? _onFinal, _onError;
  void Function()? _onSilence;

  @override
  bool get available => _ok;

  @override
  Future<bool> init() async {
    if (_ok) return true;
    try {
      _ok = await _stt.initialize(onError: _handleError, onStatus: _handleStatus);
    } catch (e) {
      debugPrint('STT init failed: $e');
      _ok = false;
    }
    return _ok;
  }

  void _settle(void Function() fire) {
    if (_settled) return;
    _settled = true;
    fire();
  }

  void _handleError(SpeechRecognitionError e) {
    final msg = e.errorMsg;
    final silent = msg == 'error_no_match' || msg == 'error_speech_timeout';
    if (_best.isNotEmpty) {
      final text = _best;
      _settle(() => _onFinal?.call(text));
    } else if (silent) {
      _settle(() => _onSilence?.call());
    } else {
      _settle(() => _onError?.call(msg));
    }
  }

  void _handleStatus(String status) {
    if (status == 'done' || status == 'notListening') {
      final turn = _turn;
      // give a trailing final result a moment to arrive before calling it silence
      Future.delayed(const Duration(milliseconds: 350), () {
        if (turn != _turn) return;
        if (_best.isNotEmpty) {
          final text = _best;
          _settle(() => _onFinal?.call(text));
        } else {
          _settle(() => _onSilence?.call());
        }
      });
    }
  }

  @override
  Future<void> listen({
    required String locale,
    required void Function(String partial) onPartial,
    required void Function(String text) onFinal,
    required void Function() onSilence,
    required void Function(String error) onError,
    required void Function(double level) onLevel,
    void Function()? onTranscribing,
    bool usePhoneMic = false,
  }) async {
    _turn++;
    _settled = false;
    _best = '';
    _onFinal = onFinal;
    _onSilence = onSilence;
    _onError = onError;
    await _stt.listen(
      listenOptions: SpeechListenOptions(
        localeId: locale,
        listenFor: const Duration(seconds: 30),
        pauseFor: const Duration(milliseconds: 2600),
        partialResults: true,
        cancelOnError: true,
        listenMode: ListenMode.dictation,
      ),
      onSoundLevelChange: (db) => onLevel(((db + 2) / 12).clamp(0.0, 1.0)),
      onResult: (SpeechRecognitionResult r) {
        _best = r.recognizedWords;
        if (r.finalResult) {
          final text = r.recognizedWords;
          _settle(() => text.trim().isEmpty ? onSilence() : onFinal(text));
        } else {
          onPartial(r.recognizedWords);
        }
      },
    );
  }

  @override
  Future<void> stop() => _stt.stop();

  @override
  Future<void> cancel() async {
    _turn++;
    _settled = true;
    await _stt.cancel();
  }
}
