import 'dart:async';

import 'package:flutter/foundation.dart';

import '../brain/router.dart';
import '../brain/tier.dart';
import '../store/transcript_store.dart';

class Message {
  const Message({
    required this.text,
    required this.fromUser,
    required this.at,
    this.tier,
    this.detail,
    this.skillName,
    this.elapsed,
    this.pending = false,
  });

  factory Message.user(String text) =>
      Message(text: text, fromUser: true, at: DateTime.now());

  factory Message.thinking() =>
      Message(text: '', fromUser: false, at: DateTime.now(), pending: true);

  factory Message.answer(Answer a) => Message(
        text: a.text,
        fromUser: false,
        at: DateTime.now(),
        tier: a.tier,
        detail: a.detail,
        skillName: a.skillName,
        elapsed: a.elapsed,
      );

  final String text;
  final bool fromUser;
  final DateTime at;
  final Tier? tier;
  final String? detail;
  final String? skillName;
  final Duration? elapsed;
  final bool pending;

  Map<String, dynamic> toJson() => {
        'text': text,
        'fromUser': fromUser,
        'at': at.millisecondsSinceEpoch,
        if (tier != null) 'tier': tier!.name,
        if (detail != null) 'detail': detail,
        if (skillName != null) 'skill': skillName,
        if (elapsed != null) 'us': elapsed!.inMicroseconds,
      };

  /// Returns null for anything malformed. A transcript written by an older
  /// build must never stop the app from starting.
  static Message? fromJson(Object? raw) {
    if (raw is! Map) return null;
    final text = raw['text'];
    final fromUser = raw['fromUser'];
    final at = raw['at'];
    if (text is! String || fromUser is! bool || at is! int) return null;

    final tierName = raw['tier'];
    final us = raw['us'];
    return Message(
      text: text,
      fromUser: fromUser,
      at: DateTime.fromMillisecondsSinceEpoch(at),
      tier: tierName is String
          ? Tier.values.where((t) => t.name == tierName).firstOrNull
          : null,
      detail: raw['detail'] is String ? raw['detail'] as String : null,
      skillName: raw['skill'] is String ? raw['skill'] as String : null,
      elapsed: us is int ? Duration(microseconds: us) : null,
    );
  }
}

/// The transcript, and the one place an utterance turns into an answer.
class Conversation extends ChangeNotifier {
  Conversation(this._router, {TranscriptStore? store})
      : _store = store ?? MemoryTranscriptStore();

  /// Older turns are dropped past this. An assistant used daily would
  /// otherwise grow its stored transcript without limit.
  static const int keep = 300;

  final BrainRouter _router;
  final TranscriptStore _store;
  final List<Message> _messages = [];

  List<Message> get messages => List.unmodifiable(_messages);
  bool get isEmpty => _messages.isEmpty;

  Map<Tier, bool> get reach => _router.reach;

  bool _busy = false;
  bool get isBusy => _busy;

  /// Restores the previous session's transcript. Safe to call once at startup;
  /// a failure here leaves an empty transcript rather than blocking the app.
  Future<void> restore() async {
    final saved = await _store.load();
    if (saved.isEmpty) return;
    _messages
      ..clear()
      ..addAll(saved);
    notifyListeners();
  }

  /// Adds the turn and returns the answer, so a caller that knows the turn
  /// arrived by voice can speak the reply. Null when the input was ignored.
  Future<Answer?> send(String raw) async {
    final text = raw.trim();
    if (text.isEmpty || _busy) return null;

    _busy = true;
    _messages
      ..add(Message.user(text))
      ..add(Message.thinking());
    notifyListeners();

    try {
      final answer = await _router.ask(text);
      _messages
        ..removeLast()
        ..add(Message.answer(answer));
      return answer;
    } finally {
      _busy = false;
      _trim();
      notifyListeners();
      // Fire and forget: a slow disk must not hold up the reply.
      unawaited(_persist());
    }
  }

  void clear() {
    _messages.clear();
    // A cleared transcript must not leave "and in feet?" resolving against a
    // question the user can no longer see.
    _router.resetContext();
    notifyListeners();
    unawaited(_store.clear());
  }

  void _trim() {
    if (_messages.length <= keep) return;
    _messages.removeRange(0, _messages.length - keep);
  }

  Future<void> _persist() =>
      _store.save(_messages.where((m) => !m.pending).toList());
}
