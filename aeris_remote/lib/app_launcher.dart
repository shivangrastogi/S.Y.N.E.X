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
}
