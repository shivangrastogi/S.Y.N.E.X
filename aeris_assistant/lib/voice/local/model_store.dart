import 'dart:io';

import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart';
import 'package:path_provider/path_provider.dart';

/// File paths sherpa-onnx needs (it reads files, not Flutter assets).
class ModelPaths {
  const ModelPaths(this.root);
  final String root;

  String get asrEncoder => '$root/asr/encoder.int8.onnx';
  String get asrDecoder => '$root/asr/decoder.int8.onnx';
  String get asrTokens => '$root/asr/tokens.txt';
  String get vad => '$root/vad/silero_vad.onnx';
  // JARVIS voice — Supertonic 3 (MIT), male voice 9, chosen by ear 2026-11-16
  String get stDuration => '$root/tts/duration_predictor.int8.onnx';
  String get stTextEncoder => '$root/tts/text_encoder.int8.onnx';
  String get stVectorEstimator => '$root/tts/vector_estimator.int8.onnx';
  String get stVocoder => '$root/tts/vocoder.int8.onnx';
  String get stJson => '$root/tts/tts.json';
  String get stIndexer => '$root/tts/unicode_indexer.bin';
  String get stVoices => '$root/tts/voice.bin';
}

/// Copies the bundled models out of the APK once (first launch), then reuses
/// them. A stamp file marks a complete copy, so an interrupted first run is
/// redone instead of leaving a half-written model behind (aeris_remote lesson:
/// stale/partial materialised assets).
abstract final class ModelStore {
  static const version = 'models-v2';
  static const _files = [
    'asr/encoder.int8.onnx',
    'asr/decoder.int8.onnx',
    'asr/tokens.txt',
    'vad/silero_vad.onnx',
    'tts/duration_predictor.int8.onnx',
    'tts/text_encoder.int8.onnx',
    'tts/vector_estimator.int8.onnx',
    'tts/vocoder.int8.onnx',
    'tts/tts.json',
    'tts/unicode_indexer.bin',
    'tts/voice.bin',
  ];

  static Future<ModelPaths>? _ready;
  static final progress = ValueNotifier<double>(0);

  static Future<ModelPaths> ensure() => _ready ??= _prepare().catchError((Object e) {
        _ready = null; // allow a retry
        throw e;
      });

  static Future<ModelPaths> _prepare() async {
    final base = await getApplicationSupportDirectory();
    final root = '${base.path}/$version';
    final stamp = File('$root/.complete');
    if (await stamp.exists()) {
      progress.value = 1;
      return ModelPaths(root);
    }
    // free the previous model set (v1 had the Piper voice) — it's ~180 MB
    final old = Directory('${base.path}/models-v1');
    if (await old.exists()) await old.delete(recursive: true);
    final steps = _files.length;
    var done = 0;
    for (final rel in _files) {
      final data = await rootBundle.load('assets/models/$rel');
      final out = File('$root/$rel');
      await out.parent.create(recursive: true);
      await out.writeAsBytes(data.buffer.asUint8List(data.offsetInBytes, data.lengthInBytes), flush: true);
      progress.value = ++done / steps;
    }
    progress.value = 1;
    await stamp.writeAsString(DateTime.now().toIso8601String());
    return ModelPaths(root);
  }

}
