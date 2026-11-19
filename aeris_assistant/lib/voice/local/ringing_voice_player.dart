import 'package:flutter/services.dart';

/// Plays one finished sentence while the phone rings, through Android's own
/// player (android/.../calls/CallAudio.kt → RingingVoicePlayer), which can
/// send it to the earbuds only — Flutter's audio plugin can't choose a device.
abstract final class RingingVoicePlayer {
  static const _channel = MethodChannel('aeris/ringing_voice');

  /// True when the sentence was played to the end where it was meant to go.
  /// False: no earbuds, Android refused the route (AERIS then stays quiet),
  /// or it took longer than [timeout].
  static Future<bool> play(String path, {required bool earbudsOnly, required Duration timeout}) async {
    try {
      final played = await _channel
          .invokeMethod<bool>('play', {'path': path, 'earbudsOnly': earbudsOnly})
          .timeout(timeout, onTimeout: () async {
        await stop();
        return false;
      });
      return played ?? false;
    } on PlatformException {
      return false;
    } on MissingPluginException {
      return false; // not on Android
    }
  }

  static Future<void> stop() async {
    try {
      await _channel.invokeMethod<void>('stop');
    } on MissingPluginException {
      // not on Android
    }
  }
}
