// Phase A1 — always-on wake word ("Aeris"), running in a foreground-service
// isolate so it keeps listening with the app closed and the screen off.
//
// Engine: sherpa-onnx keyword spotting (zipformer 3.3M) — fully free and
// open-source (Picovoice's free tier shut down 2026-06-30), no account, no
// key, and custom keywords are plain BPE text (assets/kws/keywords.txt).
// It does WAKE DETECTION ONLY: the moment the hotword fires, the mic is
// released and the app's normal Google en-IN STT takes over — the user's
// voice stack is untouched.
//
// Mic ownership contract (one owner at a time, like the laptop's pattern
// unification rule): the spotter holds the mic in idle; ChatScreen sends
// 'pause_mic' before STT and 'resume_mic' after the conversation ends.
import 'dart:async';
import 'dart:io';
import 'dart:math' as math;
import 'dart:typed_data';
import 'package:flutter/services.dart' show rootBundle;
import 'package:flutter_foreground_task/flutter_foreground_task.dart';
import 'package:path_provider/path_provider.dart';
import 'package:record/record.dart';
import 'package:sherpa_onnx/sherpa_onnx.dart' as sherpa;
import 'package:vibration/vibration.dart';

/// Keys for FlutterForegroundTask.saveData (shared prefs visible to both
/// isolates — how toggles cross the isolate boundary).
class WakeKeys {
  static const enabled = 'wake_enabled';
  static const asleep = 'wake_asleep'; // "Aeris sleep" state, survives restart
  // A11: user-tunable wake sensitivity — 'low' | 'balanced' | 'high'.
  static const sensitivity = 'wake_sensitivity';
  // Set just before launchApp so a cold-started app knows the launch was a
  // hotword (sendDataToMain is lost when no main isolate exists yet).
  static const pendingWake = 'wake_pending_ts';
}

/// Notification button ids.
class WakeButtons {
  static const sleepToggle = 'sleep_toggle';
}

/// Events sent to the main isolate.
class WakeEvents {
  static const wake = 'wake'; // hotword detected → start listening
}

/// Commands the main isolate sends to the service.
class WakeCommands {
  static const pauseMic = 'pause_mic'; // STT needs the mic
  static const resumeMic = 'resume_mic'; // conversation over
  static const sleep = 'sleep'; // "Aeris sleep"
  static const wakeUp = 'wake_up';
}

@pragma('vm:entry-point')
void startWakeService() {
  FlutterForegroundTask.setTaskHandler(WakeTaskHandler());
}

class WakeTaskHandler extends TaskHandler {
  sherpa.KeywordSpotter? _spotter;
  sherpa.OnlineStream? _stream;
  AudioRecorder? _recorder;
  StreamSubscription<Uint8List>? _audioSub;
  bool _asleep = false;
  bool _micPaused = false;
  Timer? _failsafe; // retakes the mic only if the app never acks a wake (crash)
  bool _starting = false;

  /// sherpa-onnx needs real file paths — copy the bundled model out of the
  /// Flutter asset bundle once (skipped when already present).
  Future<String> _materialiseAssets() async {
    final dir = await getApplicationSupportDirectory();
    final kws = Directory('${dir.path}/kws');
    if (!kws.existsSync()) kws.createSync(recursive: true);
    for (final name in [
      'encoder.int8.onnx',
      'decoder.int8.onnx',
      'joiner.int8.onnx',
      'tokens.txt',
      'keywords.txt',
    ]) {
      final f = File('${kws.path}/$name');
      final data = await rootBundle.load('assets/kws/$name');
      // Size mismatch → the bundled asset changed (e.g. tuned keywords.txt);
      // re-materialise so updates actually reach the engine.
      if (!f.existsSync() || f.lengthSync() != data.lengthInBytes) {
        await f.writeAsBytes(data.buffer.asUint8List(), flush: true);
      }
    }
    return kws.path;
  }

  Future<void> _startListening() async {
    if (_starting || _audioSub != null) return;
    _starting = true;
    try {
      if (_spotter == null) {
        sherpa.initBindings();
        final p = await _materialiseAssets();
        // A11: user-tunable operating point (Assistant settings → sensitivity).
        // The spotter is built once per service run; changing it restarts the
        // service. Balanced = the retuned 2026-07-12 default.
        final sens = await FlutterForegroundTask.getData<String>(
                key: WakeKeys.sensitivity) ??
            'balanced';
        // Stage-1 runs SENSITIVE — stage-2 (speech-plausibility) is what
        // rejects noise now, so we don't have to trade deafness for silence.
        final (thresh, score) = switch (sens) {
          'high' => (0.12, 2.8), // door se / dheemi awaaz bhi
          'low' => (0.24, 2.2),  // strict — clear speech only
          _ => (0.16, 2.6),      // balanced (the July-11 live-verified zone)
        };
        _spotter = sherpa.KeywordSpotter(sherpa.KeywordSpotterConfig(
          model: sherpa.OnlineModelConfig(
            transducer: sherpa.OnlineTransducerModelConfig(
              encoder: '$p/encoder.int8.onnx',
              decoder: '$p/decoder.int8.onnx',
              joiner: '$p/joiner.int8.onnx',
            ),
            tokens: '$p/tokens.txt',
            numThreads: 1,
          ),
          keywordsFile: '$p/keywords.txt',
          // Retuned 2026-07-12 after false-wake reports: 0.12/3.0 + an
          // ungated 8x AGC was manufacturing wakes out of ambient noise.
          // The VAD-gated AGC in _onAudio does the heavy lifting for
          // genuine-but-quiet speech.
          keywordsScore: score,
          keywordsThreshold: thresh,
        ));
      }
      _stream?.free();
      _stream = _spotter!.createStream();
      _recorder ??= AudioRecorder();
      final audio = await _recorder!.startStream(const RecordConfig(
        encoder: AudioEncoder.pcm16bits,
        sampleRate: 16000,
        numChannels: 1,
        // Quiet/far speech must still wake it: hardware AGC + NS, and the
        // software AGC in _onAudio on top (OEM AGC strength varies a lot).
        autoGain: true,
        noiseSuppress: true,
        echoCancel: true,
      ));
      _audioSub = audio.listen(_onAudio);
      _notify('AERIS sun raha hai', '"Aeris" bolo — ya Sleep dabao');
    } catch (e) {
      _notify('Wake word error', e.toString());
      await _stopListening();
    } finally {
      _starting = false;
    }
  }

  // Software AGC state: slow-decaying running peak of recent speech.
  double _agcPeak = 0.05;
  DateTime _lastWakeAt = DateTime.fromMillisecondsSinceEpoch(0);

  // ── Live diagnostics (visible in `flutter run` console as I/flutter) ──
  // Grep the console for "[WAKE]". Prints a ~2s audio-health heartbeat, every
  // raw sherpa keyword hit (BEFORE stage-2), and why stage-2 rejects. This is
  // how we tell "no hit at all" from "hit but gated" without logcat spelunking.
  int _frames = 0;
  DateTime _lastStatAt = DateTime.fromMillisecondsSinceEpoch(0);

  // ── Two-stage wake (2026-07-12 v2) ─────────────────────────────────
  // v1's fixed VAD floor (0.012) was DEVICE-BLIND: with hardware noise-
  // suppression this phone's speech frames often sit below it, so the AGC
  // never engaged and the hot-threshold retune went deaf. v2:
  //   Stage 1 — a SENSITIVE spotter (per-preset threshold) + adaptive
  //             noise floor (EMA of quiet frames) driving the AGC.
  //   Stage 2 — on any hit, the last ~1.5 s must actually look like bursty
  //             speech (voiced-ratio vs the adaptive floor + max≫median
  //             dynamic range). Stationary hiss/fan fails; speech passes.
  double _noiseFloor = 0.004; // adaptive ambient estimate (EMA)
  final List<double> _rmsWindow = <double>[]; // recent frame RMS (~1.5 s)
  static const int _rmsWindowMax = 24;

  double get _voicedFloor => math.max(0.006, _noiseFloor * 2.5);

  void _onAudio(Uint8List bytes) {
    final spotter = _spotter;
    final stream = _stream;
    if (spotter == null || stream == null) return;
    // PCM16 little-endian → Float32 in [-1, 1]. ByteData (not Int16List.view):
    // the recorder's chunks sit at odd offsets inside a shared buffer, and
    // Int16List.view throws on non-2-byte-aligned offsets.
    final n = bytes.lengthInBytes ~/ 2;
    if (n == 0) return;
    final bd = ByteData.sublistView(bytes);
    final f32 = Float32List(n);
    var peak = 0.0;
    var sumSq = 0.0;
    for (var i = 0; i < n; i++) {
      final v = bd.getInt16(i * 2, Endian.little) / 32768.0;
      f32[i] = v;
      final a = v.abs();
      if (a > peak) peak = a;
      sumSq += v * v;
    }
    final rms = math.sqrt(sumSq / n);
    // Adaptive noise floor. Quiet frames: fast-follow down/around. Louder
    // frames: SLOW rise too — else a room that is loud from the start (fan/AC)
    // never lifts the floor and gets amplified forever. Over ~a minute a
    // steady fan becomes the floor and stops counting as "voiced"; bursty
    // speech rides far above it either way.
    if (rms < _noiseFloor * 3) {
      _noiseFloor = (_noiseFloor * 0.95 + rms * 0.05).clamp(0.002, 0.02);
    } else {
      _noiseFloor = (_noiseFloor * 0.998 + rms * 0.002).clamp(0.002, 0.02);
    }
    _rmsWindow.add(rms);
    if (_rmsWindow.length > _rmsWindowMax) _rmsWindow.removeAt(0);

    // ~2s audio-health heartbeat so we can SEE the signal on device.
    _frames++;
    final nowStat = DateTime.now();
    if (nowStat.difference(_lastStatAt).inMilliseconds >= 2000) {
      _lastStatAt = nowStat;
      print('[WAKE] hb frames=$_frames chunk=$n rms=${rms.toStringAsFixed(4)} '
          'peak=${peak.toStringAsFixed(3)} floor=${_noiseFloor.toStringAsFixed(4)} '
          'voicedFloor=${_voicedFloor.toStringAsFixed(4)} '
          'agcPeak=${_agcPeak.toStringAsFixed(3)} '
          'voiced=${(_rmsWindow.where((r) => r > _voicedFloor).length)}/${_rmsWindow.length}');
    }

    // AGC only on voiced frames, relative to the ADAPTIVE floor (not a fixed
    // constant — that's what went deaf on this hardware). Cap 4x.
    if (rms > _voicedFloor) {
      if (peak > _agcPeak) {
        _agcPeak = peak;
      } else {
        _agcPeak = _agcPeak * 0.995 + peak * 0.005;
      }
      if (_agcPeak > 0.015 && _agcPeak < 0.6) {
        final gain = (0.6 / _agcPeak).clamp(1.0, 4.0);
        for (var i = 0; i < n; i++) {
          f32[i] = (f32[i] * gain).clamp(-1.0, 1.0);
        }
      }
    }
    stream.acceptWaveform(samples: f32, sampleRate: 16000);
    while (spotter.isReady(stream)) {
      spotter.decode(stream);
      final res = spotter.getResult(stream);
      if (res.keyword.isNotEmpty) {
        spotter.reset(stream);
        // RAW hit — sherpa matched a keyword. If you see this but no wake, the
        // gate below is the culprit; if you NEVER see this while saying it, the
        // model/threshold/audio is (tune sensitivity or check the heartbeat).
        final plausible = _speechPlausible();
        print('[WAKE] HIT "${res.keyword}" plausible=$plausible '
            '${_stage2Metrics()}');
        // Stage 2: reject hits whose audio doesn't look like speech.
        if (!plausible) {
          _debug('stage2-reject ${res.keyword}');
          break;
        }
        // Refractory guard: ignore a second hit within 3s so one utterance /
        // a noise burst can't fire repeatedly.
        final now = DateTime.now();
        if (now.difference(_lastWakeAt).inMilliseconds < 3000) {
          print('[WAKE] refractory-skip (within 3s of last wake)');
          break;
        }
        _lastWakeAt = now;
        _debug('wake ${res.keyword}');
        print('[WAKE] >>> WAKE FIRED "${res.keyword}"');
        _onWakeWord(res.keyword);
        break;
      }
    }
  }

  /// Did the recent window contain bursty, voiced audio (speech), rather than
  /// stationary hiss the model hallucinated on?
  bool _speechPlausible() {
    if (_rmsWindow.length < 8) return true; // not enough evidence — trust it
    final sorted = List<double>.from(_rmsWindow)..sort();
    final median = sorted[sorted.length ~/ 2];
    final maxR = sorted.last;
    final vf = _voicedFloor;
    final voiced = _rmsWindow.where((r) => r > vf).length / _rmsWindow.length;
    // Speech: enough voiced frames AND bursty (peak well above the median).
    return voiced >= 0.2 && maxR >= math.max(vf * 1.5, median * 2.0);
  }

  /// The numbers behind the stage-2 decision, for the console.
  String _stage2Metrics() {
    if (_rmsWindow.isEmpty) return '(no window)';
    final sorted = List<double>.from(_rmsWindow)..sort();
    final median = sorted[sorted.length ~/ 2];
    final maxR = sorted.last;
    final vf = _voicedFloor;
    final voiced = _rmsWindow.where((r) => r > vf).length / _rmsWindow.length;
    return 'win=${_rmsWindow.length} voiced=${voiced.toStringAsFixed(2)} '
        'max=${maxR.toStringAsFixed(4)} median=${median.toStringAsFixed(4)} '
        'vf=${vf.toStringAsFixed(4)}';
  }

  /// Last decisions, visible via saved data (no logcat needed on device).
  void _debug(String msg) {
    final t = DateTime.now();
    String two(int x) => x.toString().padLeft(2, '0');
    FlutterForegroundTask.saveData(
        key: 'wake_last_debug',
        value: '${two(t.hour)}:${two(t.minute)}:${two(t.second)} $msg');
  }

  Future<void> _stopListening() async {
    await _audioSub?.cancel();
    _audioSub = null;
    try {
      await _recorder?.stop();
    } catch (_) {}
    _stream?.free();
    _stream = null;
  }

  void _onWakeWord(String keyword) async {
    // Instant physical feedback — before the app is even up.
    try {
      Vibration.vibrate(duration: 90);
    } catch (_) {}
    // Release the mic BEFORE waking the app so STT can grab it instantly.
    _micPaused = true;
    await _stopListening();
    _notify('AERIS', 'Haan, bolo…');
    await FlutterForegroundTask.saveData(
        key: WakeKeys.pendingWake,
        value: DateTime.now().millisecondsSinceEpoch);
    FlutterForegroundTask.sendDataToMain({'event': WakeEvents.wake});
    // Bring the app up (needs "display over other apps" on ColorOS).
    FlutterForegroundTask.launchApp('/');
    // Safety net: if the app never reports back (killed / crash), retake the
    // mic. Cancelled the moment the app acks by holding the mic (pauseMic) or
    // finishing (resumeMic) — so a LONG conversation never gets its mic yanked
    // back mid-turn. Replaces any prior pending failsafe.
    _failsafe?.cancel();
    _failsafe = Timer(const Duration(seconds: 30), () {
      if (_micPaused && !_asleep) {
        _micPaused = false;
        _startListening();
      }
    });
  }

  void _notify(String title, String text) {
    FlutterForegroundTask.updateService(
        notificationTitle: title, notificationText: text);
  }

  @override
  Future<void> onStart(DateTime timestamp, TaskStarter starter) async {
    _asleep =
        await FlutterForegroundTask.getData<bool>(key: WakeKeys.asleep) ??
            false;
    if (_asleep) {
      _notify('AERIS so raha hai', 'Notification se ya app se jagao');
    } else {
      await _startListening();
    }
  }

  @override
  void onRepeatEvent(DateTime timestamp) {
    // Watchdog: if we should be listening but the audio stream died, revive.
    if (!_asleep && !_micPaused && _audioSub == null) _startListening();
  }

  @override
  Future<void> onDestroy(DateTime timestamp) async {
    _failsafe?.cancel();
    await _stopListening();
    _spotter?.free();
    _spotter = null;
    _recorder?.dispose();
    _recorder = null;
  }

  @override
  void onReceiveData(Object data) async {
    if (data is! Map) return;
    switch (data['cmd']) {
      case WakeCommands.pauseMic:
        // The app is holding the mic (a conversation is live) — cancel the
        // crash failsafe so it can't restart Porcupine mid-conversation.
        _failsafe?.cancel();
        _micPaused = true;
        await _stopListening();
        break;
      case WakeCommands.resumeMic:
        _failsafe?.cancel();
        _micPaused = false;
        if (!_asleep) await _startListening();
        break;
      case WakeCommands.sleep:
        await _setAsleep(true);
        break;
      case WakeCommands.wakeUp:
        await _setAsleep(false);
        break;
    }
  }

  Future<void> _setAsleep(bool v) async {
    _asleep = v;
    await FlutterForegroundTask.saveData(key: WakeKeys.asleep, value: v);
    if (v) {
      await _stopListening();
      _notify('AERIS so raha hai', 'Notification se ya app se jagao');
    } else {
      _micPaused = false;
      await _startListening();
    }
  }

  @override
  void onNotificationButtonPressed(String id) {
    if (id == WakeButtons.sleepToggle) _setAsleep(!_asleep);
  }

  @override
  void onNotificationPressed() {
    FlutterForegroundTask.launchApp('/');
  }
}
