import 'dart:collection';

import 'package:flutter/foundation.dart';

enum LogLevel { debug, info, warn, error }

class LogEntry {
  LogEntry(this.level, this.tag, this.message) : at = DateTime.now();

  final LogLevel level;
  final String tag;
  final String message;
  final DateTime at;

  String get stamp =>
      '${at.hour.toString().padLeft(2, '0')}:'
      '${at.minute.toString().padLeft(2, '0')}:'
      '${at.second.toString().padLeft(2, '0')}';

  @override
  String toString() => '[$stamp] ${level.name.toUpperCase()} $tag — $message';
}

/// In-memory ring buffer, so a diagnostics screen can show what just happened
/// without a file, a permission, or a network round trip.
///
/// Bounded on purpose: an always-on assistant logs steadily for hours, and an
/// unbounded list is a slow leak that only shows up on the user's phone.
class AerisLog extends ChangeNotifier {
  AerisLog({this.capacity = 400});

  final int capacity;
  final Queue<LogEntry> _entries = Queue<LogEntry>();

  /// Newest first — the order a diagnostics list wants to render.
  List<LogEntry> get entries => _entries.toList(growable: false).reversed.toList();

  int get length => _entries.length;

  void log(LogLevel level, String tag, String message) {
    _entries.addLast(LogEntry(level, tag, message));
    while (_entries.length > capacity) {
      _entries.removeFirst();
    }
    if (kDebugMode) {
      debugPrint(_entries.last.toString());
    }
    notifyListeners();
  }

  void debug(String tag, String message) => log(LogLevel.debug, tag, message);
  void info(String tag, String message) => log(LogLevel.info, tag, message);
  void warn(String tag, String message) => log(LogLevel.warn, tag, message);
  void error(String tag, String message) => log(LogLevel.error, tag, message);

  void clear() {
    _entries.clear();
    notifyListeners();
  }
}

/// The app-wide instance. Swapped out in tests that assert on log output.
AerisLog log = AerisLog();
