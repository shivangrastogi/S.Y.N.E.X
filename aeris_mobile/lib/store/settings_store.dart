import 'package:flutter/material.dart' show ThemeMode;
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../core/logger.dart';
import '../transport/pairing.dart';

/// Where preferences live between runs.
///
/// Separate from [TranscriptStore] on purpose: the transcript is bulk content
/// that can be dropped without consequence, settings are small and must not be
/// lost when history is cleared.
abstract class SettingsStore {
  Future<ThemeMode> loadThemeMode();
  Future<void> saveThemeMode(ThemeMode mode);

  /// Returns [LaptopPairing.none] when nothing has been paired.
  Future<LaptopPairing> loadPairing();
  Future<void> savePairing(LaptopPairing pairing);
  Future<void> clearPairing();
}

class MemorySettingsStore implements SettingsStore {
  ThemeMode _mode = ThemeMode.system;
  LaptopPairing _pairing = LaptopPairing.none;

  @override
  Future<ThemeMode> loadThemeMode() async => _mode;

  @override
  Future<void> saveThemeMode(ThemeMode mode) async => _mode = mode;

  @override
  Future<LaptopPairing> loadPairing() async => _pairing;

  @override
  Future<void> savePairing(LaptopPairing pairing) async => _pairing = pairing;

  @override
  Future<void> clearPairing() async => _pairing = LaptopPairing.none;
}

class PrefsSettingsStore implements SettingsStore {
  PrefsSettingsStore({FlutterSecureStorage? secure})
      : _secure = secure ?? const FlutterSecureStorage();

  static const String themeKey = 'aeris.theme.v1';
  static const String hostKey = 'aeris.laptop.host.v1';
  static const String portKey = 'aeris.laptop.port.v1';

  /// The passphrase lives in the platform keystore, never in shared
  /// preferences — those are plain text on disk and this is a shared secret.
  static const String passphraseKey = 'aeris.laptop.passphrase.v1';

  final FlutterSecureStorage _secure;

  @override
  Future<ThemeMode> loadThemeMode() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final raw = prefs.getString(themeKey);
      return ThemeMode.values.where((m) => m.name == raw).firstOrNull ??
          ThemeMode.system;
    } catch (e) {
      log.warn('settings', 'could not read the theme setting: $e');
      return ThemeMode.system;
    }
  }

  @override
  Future<void> saveThemeMode(ThemeMode mode) async {
    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.setString(themeKey, mode.name);
    } catch (e) {
      log.warn('settings', 'could not save the theme setting: $e');
    }
  }

  @override
  Future<LaptopPairing> loadPairing() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final host = prefs.getString(hostKey);
      if (host == null || host.isEmpty) return LaptopPairing.none;

      final passphrase = await _secure.read(key: passphraseKey);
      if (passphrase == null || passphrase.isEmpty) {
        // Host without a secret is not a usable pairing — most likely the
        // keystore entry was cleared when the app data was.
        log.info('settings', 'laptop host saved but the passphrase is gone');
        return LaptopPairing.none;
      }

      return LaptopPairing(
        host: host,
        port: prefs.getInt(portKey) ?? LaptopPairing.defaultPort,
        passphrase: passphrase,
      );
    } catch (e) {
      log.warn('settings', 'could not read the laptop pairing: $e');
      return LaptopPairing.none;
    }
  }

  @override
  Future<void> savePairing(LaptopPairing pairing) async {
    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.setString(hostKey, pairing.host);
      await prefs.setInt(portKey, pairing.port);
      await _secure.write(key: passphraseKey, value: pairing.passphrase);
    } catch (e) {
      log.warn('settings', 'could not save the laptop pairing: $e');
    }
  }

  @override
  Future<void> clearPairing() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.remove(hostKey);
      await prefs.remove(portKey);
      await _secure.delete(key: passphraseKey);
    } catch (e) {
      log.warn('settings', 'could not clear the laptop pairing: $e');
    }
  }
}
