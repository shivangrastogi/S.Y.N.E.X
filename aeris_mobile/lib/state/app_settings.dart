import 'dart:async';

import 'package:flutter/material.dart';

import '../store/settings_store.dart';

/// App-wide preferences. Small enough that one notifier covers all of them.
class AppSettings extends ChangeNotifier {
  AppSettings({SettingsStore? store}) : _store = store ?? MemorySettingsStore();

  final SettingsStore _store;

  ThemeMode _themeMode = ThemeMode.system;
  ThemeMode get themeMode => _themeMode;

  /// Reads persisted settings. Safe to call once at startup; a failure leaves
  /// the defaults in place rather than blocking the app.
  Future<void> restore() async {
    final mode = await _store.loadThemeMode();
    if (mode == _themeMode) return;
    _themeMode = mode;
    notifyListeners();
  }

  void setThemeMode(ThemeMode mode) {
    if (mode == _themeMode) return;
    _themeMode = mode;
    notifyListeners();
    unawaited(_store.saveThemeMode(mode));
  }
}
