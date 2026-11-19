// Phase A9 — open ANY installed app by spoken name (fuzzy label match in
// PackageManager), not just a hardcoded list. See MainActivity.launchByLabel.
import 'package:flutter/services.dart';

class AppLauncher {
  static const _ch = MethodChannel('aeris/apps');

  /// Returns true if an app matching [query] was found and launched.
  static Future<bool> launch(String query) async {
    try {
      return (await _ch.invokeMethod<bool>('launch', {'query': query})) ??
          false;
    } catch (_) {
      return false;
    }
  }

  /// Labels of all launchable apps (Phase 10: the agent picks from these).
  static Future<List<String>> installed() async {
    try {
      return ((await _ch.invokeMethod<List>('list')) ?? const [])
          .cast<String>();
    } catch (_) {
      return const [];
    }
  }

  /// Open WhatsApp at [phone]'s chat with the newest gallery image (last
  /// 15 min) attached. Returns '' on success, else the reason.
  static Future<String> whatsappLatestImage(String phone) async {
    try {
      return (await _ch.invokeMethod<String>(
              'whatsappLatestImage', {'phone': phone})) ??
          'no reply';
    } catch (e) {
      return '$e';
    }
  }
}
