// H.264 → Flutter Texture bridge (Phase 4d). Wraps the native
// MediaCodec decoder (MainActivity `aeris/video` channel).
//
//   init(w,h) -> textureId  : create decoder + texture
//   feed(au)                : hand one Annex-B access unit to the decoder
//   dispose()               : tear down
import 'package:flutter/services.dart';

class VideoDecoder {
  static const _ch = MethodChannel('aeris/video');
  int? textureId;

  Future<int?> init(int width, int height) async {
    try {
      final id = await _ch.invokeMethod<int>(
          'init', {'width': width, 'height': height});
      textureId = id;
      return id;
    } catch (_) {
      textureId = null;
      return null;
    }
  }

  void feed(Uint8List au) {
    // Fire-and-forget: at 60 fps we don't await each frame.
    _ch.invokeMethod('feed', au).catchError((_) {});
  }

  Future<void> dispose() async {
    textureId = null;
    try {
      await _ch.invokeMethod('dispose');
    } catch (_) {}
  }
}
