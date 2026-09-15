// Continuity — phone side of "ek mind, do body"
// (laptop mirror: core/continuity.py; design: docs/CONTINUITY_ARCHITECTURE.md).
//
// The phone is a BODY: it sends presence beats + captured goals to the mind
// (laptop) and receives routed proactive speech (reply.route) + a privacy-
// tiered memory slice (mem.slice) for the Tier-3 Gemini brain. Everything
// rides inside the existing E2E bridge message as `extra.env` — old laptop
// builds simply ignore unknown events, so pairing compatibility is kept.
import 'dart:math';

import 'package:flutter_secure_storage/flutter_secure_storage.dart';

import 'aeris_log.dart';
import 'bridge_client.dart';

class Continuity {
  static const _store = FlutterSecureStorage();
  static const _kFacts = 'continuity_mem_facts';
  static const _kVer = 'continuity_mem_ver';

  // Dedupe LRU for inbound envelope ids (mirror of the laptop's 128).
  static final List<String> _seen = <String>[];
  static const _seenCap = 128;

  // Dart port of core/goal_system._CAPTURE_RE — keep in sync BY HAND.
  // Standing intentions only; bare "remind me / yaad dilana" stays with the
  // one-shot reminder skill exactly like on the laptop.
  static final RegExp _goalRe = RegExp(
    r'\b('
    r'follow[\s-]?up|'
    r'help me plan|plan (?:kar(?:o|na)|banao)|'
    r'keep an eye on|nazar rakh|dekhte rehna|khayal rakhna|'
    r'track karo|monitor|keep track|'
    r'pursue|work on this over|iske peeche'
    r')\b',
    caseSensitive: false,
  );

  static bool looksLikeGoal(String text) => _goalRe.hasMatch(text);

  // ── envelope builder ─────────────────────────────────────────────────
  static Map<String, dynamic> envelope(String kind, Map<String, dynamic> payload,
      {double ttlS = 120}) {
    final id = 'c_${Random().nextInt(0x7fffffff).toRadixString(16)}';
    return {
      'v': 1,
      'kind': kind,
      'id': id,
      'origin': 'phone',
      'ts': DateTime.now().millisecondsSinceEpoch / 1000.0,
      'ttl_s': ttlS,
      'payload': payload,
    };
  }

  static Future<void> _sendEnv(
      BridgeClient bridge, String kind, Map<String, dynamic> payload,
      {double ttlS = 120}) async {
    try {
      await bridge.send('',
          type: 'event', extra: {'env': envelope(kind, payload, ttlS: ttlS)});
    } catch (e) {
      AerisLog.add('continuity', 'send $kind failed: $e');
    }
  }

  // ── outbound kinds ───────────────────────────────────────────────────
  static Future<void> sendBeat(BridgeClient bridge, String state) =>
      _sendEnv(bridge, 'presence.beat', {'state': state});

  static Future<void> sendGoal(BridgeClient bridge, String text) =>
      _sendEnv(bridge, 'goal.capture', {'text': text}, ttlS: 600);

  static Future<void> requestMemory(BridgeClient bridge) =>
      _sendEnv(bridge, 'mem.request', {});

  // ── inbound dispatch ─────────────────────────────────────────────────
  /// Handle one `extra.env` map from the laptop. Returns text the phone
  /// should SPEAK + show (reply.route), or null when there is nothing to
  /// surface (mem.slice stored silently, duplicates/stale dropped).
  static Future<String?> handleEnvelope(Map<String, dynamic> env) async {
    final kind = env['kind'];
    if (kind is! String) return null;
    final id = (env['id'] ?? '') as String;
    if (id.isNotEmpty) {
      if (_seen.contains(id)) return null;
      _seen.add(id);
      while (_seen.length > _seenCap) {
        _seen.removeAt(0);
      }
    }
    final ts = (env['ts'] as num?)?.toDouble() ?? 0.0;
    final ttl = (env['ttl_s'] as num?)?.toDouble() ?? 120.0;
    final now = DateTime.now().millisecondsSinceEpoch / 1000.0;
    if ((now - ts).abs() > ttl) return null;

    final payload =
        (env['payload'] as Map?)?.cast<String, dynamic>() ?? const {};

    if (kind == 'reply.route') {
      final text = (payload['text'] ?? '') as String;
      return text.trim().isEmpty ? null : text.trim();
    }
    if (kind == 'mem.slice') {
      final facts = (payload['facts'] as List?)
              ?.whereType<String>()
              .toList(growable: false) ??
          const <String>[];
      final ver = (payload['ver'] ?? 0).toString();
      await _store.write(key: _kFacts, value: facts.join('\n'));
      await _store.write(key: _kVer, value: ver);
      AerisLog.add('continuity', 'mem slice stored (${facts.length} facts)');
      return null;
    }
    return null; // phone ignores mind-side kinds
  }

  // ── memory slice access (Tier-3 Gemini injection + settings UI) ──────
  static Future<List<String>> memoryFacts() async {
    final raw = await _store.read(key: _kFacts);
    if (raw == null || raw.trim().isEmpty) return const [];
    return raw
        .split('\n')
        .map((l) => l.trim())
        .where((l) => l.isNotEmpty)
        .toList(growable: false);
  }

  static Future<void> clearMemory() async {
    await _store.delete(key: _kFacts);
    await _store.delete(key: _kVer);
  }
}
