import 'dart:convert';
import 'dart:math' as math;

import 'package:flutter/foundation.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'models.dart';

/// Persistent app state. Everything lives on this phone only.
class Store extends ChangeNotifier {
  Store(this._prefs) {
    _load();
  }

  /// In-memory store for tests.
  Store.memory() : _prefs = null;

  final SharedPreferences? _prefs;

  Settings settings = const Settings();
  final List<ActivityEntry> activity = []; // newest first
  final List<Memory> memories = []; // newest first
  final List<Protocol> protocols = [];

  static const _kSettings = 'settings.v1';
  static const _kActivity = 'activity.v1';
  static const _kMemory = 'memory.v1';
  static const _kProtocols = 'protocols.v1';
  static const maxActivity = 400;

  static Future<Store> open() async => Store(await SharedPreferences.getInstance());

  static String newId() =>
      '${DateTime.now().microsecondsSinceEpoch.toRadixString(36)}${math.Random().nextInt(1 << 20).toRadixString(36)}';

  /// Each list loads on its own and each entry on its own, so one damaged
  /// entry costs that entry — not every memory and protocol after it. (Before
  /// 2026-11-17 one try wrapped everything: a bad activity entry left the
  /// memory list empty, and the next save overwrote the real one.) A list
  /// that can't be read at all is copied to `<key>.unreadable` first.
  void _load() {
    final p = _prefs!;
    try {
      final s = p.getString(_kSettings);
      if (s != null) settings = Settings.fromJson(jsonDecode(s) as Map<String, Object?>);
    } catch (e) {
      debugPrint('AERIS settings unreadable, using defaults: $e');
    }
    activity.addAll(_loadList(p, _kActivity, ActivityEntry.fromJson));
    memories.addAll(_loadList(p, _kMemory, Memory.fromJson));
    if (p.getString(_kProtocols) == null) {
      protocols.addAll(defaultProtocols());
    } else {
      protocols.addAll(_loadList(p, _kProtocols, Protocol.fromJson));
    }
  }

  static List<T> _loadList<T>(SharedPreferences p, String key, T Function(Map<String, Object?>) fromJson) {
    final raw = p.getString(key);
    if (raw == null || raw.isEmpty) return const [];
    final List<Object?> items;
    try {
      items = jsonDecode(raw) as List;
    } catch (e) {
      debugPrint('AERIS $key unreadable — kept a copy in $key.unreadable: $e');
      p.setString('$key.unreadable', raw);
      return const [];
    }
    final loaded = <T>[];
    for (final item in items) {
      try {
        loaded.add(fromJson(Map<String, Object?>.from(item as Map)));
      } catch (e) {
        debugPrint('AERIS skipped one damaged $key entry: $e');
      }
    }
    return loaded;
  }

  void _save(String key, Object value) {
    _prefs?.setString(key, jsonEncode(value));
  }

  // ── settings ──
  void updateSettings(Settings s) {
    settings = s;
    _save(_kSettings, s.toJson());
    notifyListeners();
  }

  // ── activity ──
  void addActivity(ActivityEntry e) {
    activity.insert(0, e);
    if (activity.length > maxActivity) activity.removeRange(maxActivity, activity.length);
    _save(_kActivity, activity.map((a) => a.toJson()).toList());
    notifyListeners();
  }

  void clearActivity() {
    activity.clear();
    _save(_kActivity, const []);
    notifyListeners();
  }

  /// Real numbers only (DESIGN R1).
  ({int today, int avgMs}) stats() {
    final now = DateTime.now();
    final todays = activity.where((a) =>
        a.at.year == now.year && a.at.month == now.month && a.at.day == now.day);
    final ok = activity.where((a) => a.status == TurnStatus.ok).take(50).toList();
    final avg = ok.isEmpty ? 0 : ok.map((a) => a.latencyMs).reduce((a, b) => a + b) ~/ ok.length;
    return (today: todays.length, avgMs: avg);
  }

  // ── memory ──
  Memory addMemory(String text) {
    final m = Memory(id: newId(), text: text.trim(), createdAt: DateTime.now());
    memories.insert(0, m);
    _saveMemories();
    return m;
  }

  void updateMemory(Memory m) {
    final i = memories.indexWhere((x) => x.id == m.id);
    if (i < 0) return;
    memories[i] = m;
    _saveMemories();
  }

  void removeMemory(String id) {
    memories.removeWhere((m) => m.id == id);
    _saveMemories();
  }

  void restoreMemory(Memory m, int index) {
    memories.insert(index.clamp(0, memories.length), m);
    _saveMemories();
  }

  void clearMemories() {
    memories.clear();
    _saveMemories();
  }

  void _saveMemories() {
    _save(_kMemory, memories.map((m) => m.toJson()).toList());
    notifyListeners();
  }

  // ── protocols ──
  void upsertProtocol(Protocol p) {
    final i = protocols.indexWhere((x) => x.id == p.id);
    if (i < 0) {
      protocols.add(p);
    } else {
      protocols[i] = p;
    }
    _saveProtocols();
  }

  void removeProtocol(String id) {
    protocols.removeWhere((p) => p.id == id);
    _saveProtocols();
  }

  void restoreProtocol(Protocol p, int index) {
    protocols.insert(index.clamp(0, protocols.length), p);
    _saveProtocols();
  }

  void _saveProtocols() {
    _save(_kProtocols, protocols.map((p) => p.toJson()).toList());
    notifyListeners();
  }

  static List<Protocol> defaultProtocols() => [
        Protocol(
          id: 'p_morning',
          name: 'Good morning',
          phrase: 'good morning',
          actions: const ['time batao', 'aaj ki date', 'battery kitni hai'],
          sayAfter: 'Have a great day.',
        ),
        // Focus now really goes quiet (vibrate) — it used to promise "I will
        // stay quiet" and change nothing (review, 2026-11-17).
        Protocol(
          id: 'p_focus',
          name: 'Focus',
          phrase: 'focus mode',
          actions: const ['25 minute ka timer lagao', 'phone vibrate pe karo'],
          sayAfter: 'Focus timer started, phone on vibrate.',
        ),
        Protocol(
          id: 'p_night',
          name: 'Night',
          phrase: 'good night',
          actions: const ['torch off', 'kal subah 7 baje ka alarm laga do'],
          sayAfter: 'Sleep well.',
          enabled: false,
        ),
      ];
}
