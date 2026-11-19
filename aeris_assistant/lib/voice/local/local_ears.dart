import 'dart:async';
import 'dart:math' as math;

import 'package:flutter/foundation.dart';
import 'package:permission_handler/permission_handler.dart';
import 'package:record/record.dart';
import 'package:sherpa_onnx/sherpa_onnx.dart' as so;

import '../io.dart';
import '../translit.dart';
import 'model_store.dart';
import 'speech_worker.dart';

/// AERIS's own ears: raw mic via `record` (no system recognizer → no Google
/// beep, nothing leaves the phone) → Silero VAD finds where you start/stop →
/// the Hinglish Whisper model in [SpeechWorker] writes it down →
/// [cleanTranscript] fixes known mishearings.
class LocalEars implements Ears {
  final _rec = AudioRecorder();

  /// The phone's own microphone (record lists it as "… (built-in microphone…)").
  Future<InputDevice?> _phoneMic() async {
    try {
      final inputs = await _rec.listInputDevices();
      return inputs.where((device) => device.label.contains('built-in microphone')).firstOrNull;
    } catch (e) {
      debugPrint('mic list failed: $e');
      return null;
    }
  }
  so.VoiceActivityDetector? _vad;
  SpeechWorker? _worker;
  bool _ok = false;

  int _turn = 0;
  StreamSubscription<Uint8List>? _sub;
  Timer? _noSpeech, _maxLen;
  final _all = <double>[]; // whole turn, fallback if VAD never closes a segment
  final _win = <double>[]; // VAD window accumulator
  bool _speech = false;
  bool _settled = true;
  void Function()? _finishNow; // decode what was said so far

  static const _rate = 16000;
  static const _window = 512;

  // Whisper's classic phantom outputs on near-silence.
  static const _phantoms = {'thank you', 'thanks', 'thanks for watching', 'you', 'bye', 'subscribe', '.'};

  @override
  bool get available => _ok;

  @override
  Future<bool> init() async {
    if (_ok) return true;
    try {
      if (!await Permission.microphone.request().isGranted) return false;
      final paths = await ModelStore.ensure();
      so.initBindings();
      _vad ??= so.VoiceActivityDetector(
        config: so.VadModelConfig(
          sileroVad: so.SileroVadModelConfig(
            model: paths.vad,
            threshold: 0.5,
            minSilenceDuration: 0.8, // pause that ends a command
            minSpeechDuration: 0.2,
            maxSpeechDuration: 20,
            windowSize: _window,
          ),
          numThreads: 1,
          debug: false,
        ),
        bufferSizeInSeconds: 30,
      );
      _worker = await SpeechWorker.get(paths);
      unawaited(_worker!.warm());
      _ok = true;
    } catch (e) {
      debugPrint('LocalEars init failed: $e');
      _ok = false;
    }
    return _ok;
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
    await _stopMic();
    final turn = ++_turn;
    _settled = false;
    _speech = false;
    _all.clear();
    _win.clear();
    _vad!.clear();

    void settle(void Function() fire) {
      if (_settled || turn != _turn) return;
      _settled = true;
      _noSpeech?.cancel();
      _maxLen?.cancel();
      fire();
    }

    Future<void> finish(Float32List samples) async {
      if (_settled || turn != _turn) return;
      _settled = true;
      _noSpeech?.cancel();
      _maxLen?.cancel();
      await _stopMic();
      onLevel(0);
      onTranscribing?.call();
      try {
        final raw = await _worker!.transcribe(samples);
        if (turn != _turn) return;
        final text = cleanTranscript(raw);
        final secs = samples.length / _rate;
        if (text.isEmpty || (_phantoms.contains(text) && secs < 1.2)) {
          onSilence();
        } else {
          onFinal(text);
        }
      } catch (e) {
        if (turn == _turn) onError('$e');
      }
    }

    final Stream<Uint8List> stream;
    try {
      final phoneMic = usePhoneMic ? await _phoneMic() : null;
      stream = await _rec.startStream(RecordConfig(
        encoder: AudioEncoder.pcm16bits,
        sampleRate: _rate,
        numChannels: 1,
        autoGain: true,
        noiseSuppress: true,
        device: phoneMic,
        // VOICE_RECOGNITION follows a Bluetooth headset; plain MIC + the chosen
        // device keeps it on the phone
        androidConfig: AndroidRecordConfig(
            audioSource: phoneMic == null ? AndroidAudioSource.voiceRecognition : AndroidAudioSource.mic),
      ));
    } catch (e) {
      settle(() => onError('mic: $e'));
      return;
    }

    // nothing said within 7 s → silence; any command longer than 15 s is cut
    _noSpeech = Timer(const Duration(seconds: 7), () {
      if (!_speech) {
        _stopMic();
        settle(onSilence);
      }
    });
    _finishNow = () {
      _vad!.flush();
      final seg = _vad!.isEmpty() ? Float32List.fromList(_all) : _vad!.front().samples;
      if (!_vad!.isEmpty()) _vad!.pop();
      finish(seg);
    };
    _maxLen = Timer(const Duration(seconds: 15), () => _finishNow?.call());

    _sub = stream.listen((chunk) {
      if (turn != _turn || _settled) return;
      // PCM16 LE → float. sublistView: record's chunks can be odd-offset views
      // (aeris_remote lesson — never Int16List.view).
      final bd = ByteData.sublistView(chunk);
      final n = chunk.lengthInBytes ~/ 2;
      var sumSq = 0.0;
      for (var i = 0; i < n; i++) {
        final v = bd.getInt16(i * 2, Endian.little) / 32768.0;
        sumSq += v * v;
        _win.add(v);
        _all.add(v);
      }
      if (n > 0) onLevel((math.sqrt(sumSq / n) * 6).clamp(0.0, 1.0));

      while (_win.length >= _window) {
        _vad!.acceptWaveform(Float32List.fromList(_win.sublist(0, _window)));
        _win.removeRange(0, _window);
        if (_vad!.isDetected()) _speech = true;
        if (!_vad!.isEmpty()) {
          final seg = _vad!.front().samples;
          _vad!.pop();
          finish(seg);
          return;
        }
      }
    });
  }

  Future<void> _stopMic() async {
    await _sub?.cancel();
    _sub = null;
    try {
      if (await _rec.isRecording()) await _rec.stop();
    } catch (_) {}
  }

  /// Stop early: decode whatever was said so far.
  @override
  Future<void> stop() async {
    if (!_settled && _speech) {
      _finishNow?.call();
    } else {
      await cancel();
    }
  }

  @override
  Future<void> cancel() async {
    _turn++;
    _settled = true;
    _noSpeech?.cancel();
    _maxLen?.cancel();
    await _stopMic();
  }
}
