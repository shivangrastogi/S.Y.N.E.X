// Phone screen capture via native Android MediaProjection.
//
// Bridges to MainActivity.kt over a MethodChannel. Capturing the whole
// device screen (not just this app) needs the system screen-record
// permission — the first captureOnce() pops the OS dialog; the grant is
// reused for the session.
import 'package:flutter/services.dart';

class ScreenCapture {
  static const _ch = MethodChannel('aeris/screencap');

  /// Ask for the screen-capture permission (OS dialog). Returns true if
  /// granted. Safe to call repeatedly — no-op once granted.
  static Future<bool> ensurePermission() async {
    try {
      final ok = await _ch.invokeMethod<bool>('ensurePermission');
      return ok ?? false;
    } catch (_) {
      return false;
    }
  }

  /// Capture one frame of the whole screen as JPEG bytes, or null.
  static Future<Uint8List?> captureOnce() async {
    try {
      if (!await ensurePermission()) return null;
      final bytes = await _ch.invokeMethod<Uint8List>('captureOnce');
      return bytes;
    } catch (_) {
      return null;
    }
  }
}
