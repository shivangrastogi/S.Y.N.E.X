/// Plain data. Everything serialises to JSON for shared_preferences.
library;

enum TurnStatus { ok, failed, cancelled, unknown }

/// One handled command — the Log screen and transparency detail.
class ActivityEntry {
  ActivityEntry({
    required this.id,
    required this.at,
    required this.said,
    required this.tool,
    required this.args,
    required this.reply,
    required this.status,
    required this.latencyMs,
    this.tier = 'device',
    this.typed = false,
  });

  final String id;
  final DateTime at;
  final String said;
  final String tool;
  final Map<String, Object?> args;
  final String reply;
  final TurnStatus status;
  final int latencyMs;
  final String tier;
  final bool typed;

  Map<String, Object?> toJson() => {
        'id': id,
        'at': at.toIso8601String(),
        'said': said,
        'tool': tool,
        'args': args,
        'reply': reply,
        'status': status.name,
        'ms': latencyMs,
        'tier': tier,
        'typed': typed,
      };

  static ActivityEntry fromJson(Map<String, Object?> j) => ActivityEntry(
        id: j['id'] as String,
        at: DateTime.parse(j['at'] as String),
        said: j['said'] as String? ?? '',
        tool: j['tool'] as String? ?? 'unknown',
        args: Map<String, Object?>.from(j['args'] as Map? ?? const {}),
        reply: j['reply'] as String? ?? '',
        status: TurnStatus.values.asNameMap()[j['status']] ?? TurnStatus.ok,
        latencyMs: (j['ms'] as num?)?.toInt() ?? 0,
        tier: j['tier'] as String? ?? 'device',
        typed: j['typed'] as bool? ?? false,
      );
}

/// Something the user asked AERIS to remember.
class Memory {
  Memory({required this.id, required this.text, required this.createdAt, DateTime? updatedAt})
      : updatedAt = updatedAt ?? createdAt;
  final String id;
  final String text;
  final DateTime createdAt;
  final DateTime updatedAt;

  Memory copyWith({String? text}) =>
      Memory(id: id, text: text ?? this.text, createdAt: createdAt, updatedAt: DateTime.now());

  Map<String, Object?> toJson() => {
        'id': id,
        'text': text,
        'c': createdAt.toIso8601String(),
        'u': updatedAt.toIso8601String(),
      };

  static Memory fromJson(Map<String, Object?> j) => Memory(
        id: j['id'] as String,
        text: j['text'] as String,
        createdAt: DateTime.parse(j['c'] as String),
        updatedAt: DateTime.tryParse(j['u'] as String? ?? ''),
      );
}

/// "One phrase, many actions." Each action is a command AERIS already
/// understands, run through the same router.
class Protocol {
  Protocol({
    required this.id,
    required this.name,
    required this.phrase,
    required this.actions,
    this.sayAfter = '',
    this.enabled = true,
  });
  final String id;
  final String name;
  final String phrase;
  final List<String> actions;
  final String sayAfter;
  final bool enabled;

  Protocol copyWith({String? name, String? phrase, List<String>? actions, String? sayAfter, bool? enabled}) =>
      Protocol(
        id: id,
        name: name ?? this.name,
        phrase: phrase ?? this.phrase,
        actions: actions ?? this.actions,
        sayAfter: sayAfter ?? this.sayAfter,
        enabled: enabled ?? this.enabled,
      );

  Map<String, Object?> toJson() => {
        'id': id,
        'name': name,
        'phrase': phrase,
        'actions': actions,
        'say': sayAfter,
        'on': enabled,
      };

  static Protocol fromJson(Map<String, Object?> j) => Protocol(
        id: j['id'] as String,
        name: j['name'] as String,
        phrase: j['phrase'] as String,
        actions: List<String>.from(j['actions'] as List? ?? const []),
        sayAfter: j['say'] as String? ?? '',
        enabled: j['on'] as bool? ?? true,
      );
}

enum Lang { hinglish, englishIn, englishUs }

/// Who turns speech into text. AERIS = on-device (default), Google = Android's recognizer.
enum SttEngine { aeris, google }

class Settings {
  const Settings({
    this.name = '',
    this.lang = Lang.hinglish,
    this.speak = true,
    this.keepListening = true,
    this.rate = 0.5,
    this.onboarded = false,
    this.voice = 'jarvis',
    this.stt = SttEngine.aeris,
    this.callsByVoice = false,
  });
  final String name;
  final Lang lang;
  final bool speak;
  final bool keepListening;
  final double rate; // Android TTS: 0.5 = normal
  final bool onboarded;

  /// Voice id (edge neural voice, or 'device' for the offline phone voice).
  final String voice;
  final SttEngine stt;

  /// Announce incoming calls and answer / decline them by voice (lib/calls/).
  final bool callsByVoice;

  Settings copyWith({
    String? name,
    Lang? lang,
    bool? speak,
    bool? keepListening,
    double? rate,
    bool? onboarded,
    String? voice,
    SttEngine? stt,
    bool? callsByVoice,
  }) =>
      Settings(
        name: name ?? this.name,
        lang: lang ?? this.lang,
        speak: speak ?? this.speak,
        keepListening: keepListening ?? this.keepListening,
        rate: rate ?? this.rate,
        onboarded: onboarded ?? this.onboarded,
        voice: voice ?? this.voice,
        stt: stt ?? this.stt,
        callsByVoice: callsByVoice ?? this.callsByVoice,
      );

  Map<String, Object?> toJson() => {
        'name': name,
        'lang': lang.name,
        'speak': speak,
        'keep': keepListening,
        'rate': rate,
        'onb': onboarded,
        'voice': voice,
        'stt': stt.name,
        'calls': callsByVoice,
      };

  static Settings fromJson(Map<String, Object?> j) => Settings(
        name: j['name'] as String? ?? '',
        lang: Lang.values.asNameMap()[j['lang']] ?? Lang.hinglish,
        speak: j['speak'] as bool? ?? true,
        keepListening: j['keep'] as bool? ?? true,
        rate: (j['rate'] as num?)?.toDouble() ?? 0.5,
        onboarded: j['onb'] as bool? ?? false,
        // settings saved before the own-stack switch (no 'stt' key) move to
        // the JARVIS voice + on-device ears — Shivang's 2026-11-16 choice
        voice: 'jarvis', // one voice only (2026-11-17) — any older choice moves to it
        stt: SttEngine.values.asNameMap()[j['stt']] ?? SttEngine.aeris,
        callsByVoice: j['calls'] as bool? ?? false,
      );
}
