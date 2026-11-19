// Laptop → phone actions: ring (find my phone) + battery report.
//
// The laptop sends type='phone_action' messages over the bridge (app
// open) AND FCM pushes (app closed). This handles the in-app side; the
// FCM background handler in main.dart covers the closed-app ring.
import 'dart:convert';
import 'package:audioplayers/audioplayers.dart';
import 'package:battery_plus/battery_plus.dart';
import 'package:vibration/vibration.dart';
import 'bridge_client.dart';
import 'screen_capture.dart';

class PhoneActions {
  static final AudioPlayer _player = AudioPlayer();
  static bool _ringing = false;

  /// Ring loudly + vibrate until stopped. Uses a bundled tone; if that
  /// asset is missing it still vibrates so the phone is findable.
  static Future<void> ring() async {
    if (_ringing) return;
    _ringing = true;
    try {
      await _player.setReleaseMode(ReleaseMode.loop);
      await _player.setVolume(1.0);
      await _player.play(AssetSource('ring.mp3'));
    } catch (_) {/* no asset — vibration below still fires */}
    try {
      if (await Vibration.hasVibrator()) {
        Vibration.vibrate(pattern: [0, 600, 300, 600, 300, 600], repeat: 1);
      }
    } catch (_) {}
  }

  static Future<void> stopRing() async {
    _ringing = false;
    try {
      await _player.stop();
    } catch (_) {}
    try {
      Vibration.cancel();
    } catch (_) {}
  }

  static Future<Map<String, dynamic>> batteryStatus() async {
    final b = Battery();
    try {
      final level = await b.batteryLevel;
      final state = await b.batteryState;
      return {
        'battery': level,
        'charging': state == BatteryState.charging ||
            state == BatteryState.full,
      };
    } catch (_) {
      return {'battery': -1, 'charging': false};
    }
  }

  /// Dispatch an incoming phone_action from the laptop.
  static Future<void> handle(BridgeMessage m, BridgeClient bridge) async {
    final action = (m.extra['action'] ?? m.text).toString();
    switch (action) {
      case 'ring':
        await ring();
        break;
      case 'stop_ring':
        await stopRing();
        break;
      case 'get_battery':
        await bridge.sendStatus(await batteryStatus());
        break;
      case 'request_screen':
        // Laptop wants to see the phone screen — capture + send it back.
        final bytes = await ScreenCapture.captureOnce();
        if (bytes != null) {
          await bridge.send('Phone screen', type: 'phone_screen',
              extra: {'format': 'jpeg', 'b64': base64Encode(bytes)});
        }
        break;
    }
  }
}
