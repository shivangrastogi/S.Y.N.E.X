import 'dart:convert';

import 'package:shared_preferences/shared_preferences.dart';

import '../core/logger.dart';
import '../state/conversation.dart';

/// Where the transcript lives between runs.
///
/// Behind an interface for the same reason voice is: tests and any platform
/// without the plugin get a working in-memory version rather than a crash.
abstract class TranscriptStore {
  Future<List<Message>> load();
  Future<void> save(List<Message> messages);
  Future<void> clear();
}

/// Keeps the transcript for the life of the process only — the default, and
/// what every test uses.
class MemoryTranscriptStore implements TranscriptStore {
  List<Message> _saved = const [];

  @override
  Future<List<Message>> load() async => _saved;

  @override
  Future<void> save(List<Message> messages) async => _saved = List.of(messages);

  @override
  Future<void> clear() async => _saved = const [];
}

/// Persists to shared preferences as a JSON array.
///
/// Every failure path returns an empty transcript rather than throwing: losing
/// history is a small annoyance, failing to start is not.
class PrefsTranscriptStore implements TranscriptStore {
  static const String key = 'aeris.transcript.v1';

  @override
  Future<List<Message>> load() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final raw = prefs.getString(key);
      if (raw == null || raw.isEmpty) return const [];

      final decoded = jsonDecode(raw);
      if (decoded is! List) return const [];

      // Individually nullable: one unreadable entry from an older build drops
      // that entry, not the whole history.
      return decoded
          .map(Message.fromJson)
          .whereType<Message>()
          .toList(growable: false);
    } catch (e) {
      log.warn('store', 'could not read the saved transcript: $e');
      return const [];
    }
  }

  @override
  Future<void> save(List<Message> messages) async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final raw = jsonEncode([for (final m in messages) m.toJson()]);
      await prefs.setString(key, raw);
    } catch (e) {
      log.warn('store', 'could not save the transcript: $e');
    }
  }

  @override
  Future<void> clear() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.remove(key);
    } catch (e) {
      log.warn('store', 'could not clear the saved transcript: $e');
    }
  }
}
