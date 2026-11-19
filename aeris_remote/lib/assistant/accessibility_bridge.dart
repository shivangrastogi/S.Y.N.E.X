// Phase A5 — Dart side of the screen-control AccessibilityService.
// Thin wrapper over the aeris/a11y method channel (see MainActivity.kt).
import 'package:flutter/services.dart';

class AccessibilityBridge {
  static const _ch = MethodChannel('aeris/a11y');

  static Future<bool> isEnabled() async =>
      (await _ch.invokeMethod<bool>('isEnabled')) ?? false;

  static Future<void> openSettings() => _ch.invokeMethod('openSettings');

  static Future<String> readScreen() async =>
      (await _ch.invokeMethod<String>('readScreen')) ?? '';

  static Future<bool> tap(String text) async =>
      (await _ch.invokeMethod<bool>('tap', {'text': text})) ?? false;

  static Future<bool> scroll({required bool forward}) async =>
      (await _ch.invokeMethod<bool>('scroll', {'forward': forward})) ?? false;

  /// action: back | home | recents | notifications | quick_settings
  static Future<bool> global(String action) async =>
      (await _ch.invokeMethod<bool>('global', {'action': action})) ?? false;

  // ── Phase 10: phone agent. Elements are addressed by the [n] ids of the
  // most recent dumpUi(); call dumpUi() again after anything changes.

  /// "app: <package>" then one `[n] Class "label" actions` line per element.
  static Future<String> dumpUi() async =>
      (await _ch.invokeMethod<String>('dumpUi')) ?? '';

  static Future<bool> clickId(int id) async =>
      (await _ch.invokeMethod<bool>('clickId', {'id': id})) ?? false;

  static Future<bool> longClickId(int id) async =>
      (await _ch.invokeMethod<bool>('longClickId', {'id': id})) ?? false;

  /// Replaces the field's text; id < 0 targets the focused input.
  static Future<bool> typeId(int id, String text) async =>
      (await _ch.invokeMethod<bool>('typeId', {'id': id, 'text': text})) ??
      false;

  static Future<bool> pressEnter() async =>
      (await _ch.invokeMethod<bool>('pressEnter')) ?? false;

  /// key: playpause | next | prev | stop
  static Future<void> media(String key) =>
      _ch.invokeMethod('media', {'key': key});
}
