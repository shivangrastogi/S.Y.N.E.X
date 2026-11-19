import 'dart:async';
import 'dart:isolate';
import 'dart:typed_data';

import 'package:sherpa_onnx/sherpa_onnx.dart' as so;

import 'model_store.dart';

/// One long-lived background isolate that owns the heavy native models:
/// the Hinglish Whisper recognizer and the JARVIS voice (Supertonic 3). The UI isolate
/// only sends samples/text and gets results back — the reactor never stutters
/// while AERIS thinks (BUILD_GUIDE §12.7).
class SpeechWorker {
  SpeechWorker._(this._send, this._rx);
  final SendPort _send;
  final ReceivePort _rx;
  final _pending = <int, Completer<Object?>>{};
  var _id = 0;

  static Future<SpeechWorker>? _instance;

  static Future<SpeechWorker> get(ModelPaths paths) => _instance ??= _spawn(paths);

  static Future<SpeechWorker> _spawn(ModelPaths paths) async {
    final rx = ReceivePort();
    final ready = Completer<SendPort>();
    late SpeechWorker w;
    rx.listen((msg) {
      if (msg is SendPort) {
        ready.complete(msg);
      } else if (msg is List && msg.length == 3) {
        final c = w._pending.remove(msg[0] as int);
        if (c == null) return;
        msg[1] == null ? c.complete(msg[2]) : c.completeError(StateError('${msg[1]}'));
      }
    });
    await Isolate.spawn(_main, [rx.sendPort, paths.root], debugName: 'aeris-speech');
    w = SpeechWorker._(await ready.future, rx);
    return w;
  }

  Future<Object?> _call(String op, Object? arg) {
    final id = _id++;
    final c = Completer<Object?>();
    _pending[id] = c;
    _send.send([id, op, arg]);
    return c.future;
  }

  /// Shut the worker's inbox (the isolate exits when its port closes).
  void dispose() => _rx.close();

  /// Load both models now so the first command isn't slow.
  Future<void> warm() => _call('warm', null);

  /// 16 kHz mono float samples → raw transcript.
  Future<String> transcribe(Float32List samples) async =>
      (await _call('asr', TransferableTypedData.fromList([samples]))) as String;

  /// Text → WAV file at [path]; returns the audio length in ms.
  /// [lang] is Supertonic's language ('hi' for Devanagari Hinglish, 'en').
  Future<int> synth(String text, {required double speed, required String lang, required String path, int sid = 7}) async =>
      (await _call('tts', [text, speed, path, lang, sid])) as int;

  /// Benchmark: recognizer ms for [samples] with [threads].
  Future<int> asrBench(Float32List samples, int threads) async =>
      (await _call('asrbench', [TransferableTypedData.fromList([samples]), threads])) as int;

  /// Benchmark: generation ms for [text] with a given thread count and step
  /// count (rebuilds the voice when the thread count changes). Returns
  /// [genMs, audioMs].
  Future<List<int>> bench(String text, {required int threads, required int steps, required String lang, int sid = 7, double speed = 1.0}) async =>
      ((await _call('bench', [text, threads, steps, lang, sid, speed])) as List).cast<int>();

  // ── isolate side ──
  static void _main(List<Object?> args) {
    final out = args[0] as SendPort;
    final paths = ModelPaths(args[1] as String);
    final inbox = ReceivePort();
    out.send(inbox.sendPort);

    so.initBindings();
    so.OfflineRecognizer? rec;
    so.OfflineTts? tts;
    // Measured on the RMX3741 (2026-11-17 self-test): 2 threads is fastest —
    // the 6 little cores only add contention. 4 threads was 1.6× slower.
    var ttsThreads = 2;
    var asrThreads = 2;

    so.OfflineRecognizer recognizer() => rec ??= so.OfflineRecognizer(so.OfflineRecognizerConfig(
          model: so.OfflineModelConfig(
            whisper: so.OfflineWhisperModelConfig(
              encoder: paths.asrEncoder,
              decoder: paths.asrDecoder,
              language: 'en', // Hinglish-Swift was measured best with "en" (tool/model_export)
              task: 'transcribe',
            ),
            tokens: paths.asrTokens,
            numThreads: asrThreads,
            debug: false,
          ),
        ));

    so.OfflineTts voice() => tts ??= so.OfflineTts(so.OfflineTtsConfig(
          model: so.OfflineTtsModelConfig(
            supertonic: so.OfflineTtsSupertonicModelConfig(
              durationPredictor: paths.stDuration,
              textEncoder: paths.stTextEncoder,
              vectorEstimator: paths.stVectorEstimator,
              vocoder: paths.stVocoder,
              ttsJson: paths.stJson,
              unicodeIndexer: paths.stIndexer,
              voiceStyle: paths.stVoices,
            ),
            numThreads: ttsThreads,
            debug: false,
          ),
        ));

    inbox.listen((msg) {
      final m = msg as List;
      final id = m[0] as int;
      try {
        switch (m[1] as String) {
          case 'warm':
            recognizer();
            voice();
            out.send([id, null, null]);
          case 'asr':
            final samples = (m[2] as TransferableTypedData).materialize().asFloat32List();
            final r = recognizer();
            final s = r.createStream();
            s.acceptWaveform(samples: samples, sampleRate: 16000);
            r.decode(s);
            final text = r.getResult(s).text;
            s.free();
            out.send([id, null, text]);
          case 'tts':
            final a = m[2] as List;
            final audio = voice().generateWithConfig(
              text: a[0] as String,
              config: so.OfflineTtsGenerationConfig(
                sid: a[4] as int,
                speed: a[1] as double,
                numSteps: 8, // = the sample Shivang picked; repeat phrases come from VoiceCache
                extra: {'lang': a[3] as String},
              ),
            );
            so.writeWave(filename: a[2] as String, samples: audio.samples, sampleRate: audio.sampleRate);
            final ms = audio.sampleRate == 0 ? 0 : (audio.samples.length * 1000 ~/ audio.sampleRate);
            out.send([id, null, ms]);
          case 'asrbench':
            final a = m[2] as List;
            final threads = a[1] as int;
            if (threads != asrThreads) {
              rec?.free();
              rec = null;
              asrThreads = threads;
            }
            final samples = (a[0] as TransferableTypedData).materialize().asFloat32List();
            final r0 = recognizer();
            final w0 = r0.createStream()..acceptWaveform(samples: samples, sampleRate: 16000);
            r0.decode(w0); // warm
            w0.free();
            final t = Stopwatch()..start();
            final s = r0.createStream()..acceptWaveform(samples: samples, sampleRate: 16000);
            r0.decode(s);
            s.free();
            out.send([id, null, t.elapsedMilliseconds]);
          case 'bench':
            final a = m[2] as List;
            final threads = a[1] as int;
            if (threads != ttsThreads) {
              tts?.free();
              tts = null;
              ttsThreads = threads;
            }
            final v = voice();
            v.generateWithConfig(text: 'ok', config: so.OfflineTtsGenerationConfig(sid: a[4] as int, numSteps: a[2] as int, extra: {'lang': a[3] as String}));
            final t = Stopwatch()..start();
            final audio = v.generateWithConfig(
              text: a[0] as String,
              config: so.OfflineTtsGenerationConfig(
                  sid: a[4] as int, speed: a[5] as double, numSteps: a[2] as int, extra: {'lang': a[3] as String}),
            );
            final ms = t.elapsedMilliseconds;
            out.send([id, null, [ms, audio.samples.length * 1000 ~/ audio.sampleRate]]);
          default:
            out.send([id, 'unknown op', null]);
        }
      } catch (e) {
        out.send([id, '$e', null]);
      }
    });
  }
}
