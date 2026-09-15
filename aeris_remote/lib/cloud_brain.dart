// Phase A3 — Tier-3 cloud brain. When the laptop (Tier-2) is offline, general
// questions go to Google's Gemini via the free Developer API: knowledge,
// reasoning, and — where the key's tier allows it — live web answers.
//
// Free tier answers text for free; "grounding" (live Google Search) is a paid
// feature on 2.5 models (free only on 3.x, 5k/month). So we TRY with grounding
// and, if the tier rejects it, transparently retry without — the user still
// gets a smart answer, just from the model's own knowledge.
import 'dart:convert';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:http/http.dart' as http;
import 'aeris_log.dart';
import 'continuity.dart';

class CloudBrain {
  static const _kKey = 'gemini_api_key';
  static const _kModel = 'gemini_model';
  static const _kGround = 'gemini_grounding';
  static const _defaultModel = 'gemini-2.5-flash';
  static const _store = FlutterSecureStorage();

  // Spoken-first, Hinglish — matches the user's voice stack. Short answers,
  // because they get read aloud by TTS.
  static const _system =
      'Tum AERIS ho, ek helpful voice assistant. Hinglish (Roman Hindi + '
      'English) mein jawab do, jaise ek dost baat karta hai. Jawab CHOTA aur '
      'seedha rakho — 1 se 3 lines, kyunki ye bol kar sunaya jayega. Lists, '
      'markdown ya symbols mat use karo, saaf bolne wale vaakya likho. Agar '
      'pakka nahi pata to keh do.';

  static Future<bool> get isConfigured async =>
      (await _store.read(key: _kKey))?.isNotEmpty ?? false;

  static Future<String> get apiKey async =>
      (await _store.read(key: _kKey)) ?? '';
  static Future<void> setApiKey(String k) =>
      _store.write(key: _kKey, value: k.trim());

  static Future<String> get model async =>
      (await _store.read(key: _kModel))?.trim().isNotEmpty == true
          ? (await _store.read(key: _kModel))!.trim()
          : _defaultModel;
  static Future<void> setModel(String m) =>
      _store.write(key: _kModel, value: m.trim());

  static Future<bool> get grounding async =>
      (await _store.read(key: _kGround)) != 'off';
  static Future<void> setGrounding(bool on) =>
      _store.write(key: _kGround, value: on ? 'on' : 'off');

  /// Ask the cloud brain. [history] is prior turns ({role: user|model, text})
  /// so follow-ups like "uska matlab kya hai" keep context. Returns a
  /// spoken-ready answer, or a short error.
  static Future<String> ask(String question,
      {List<Map<String, String>> history = const []}) async {
    final key = await apiKey;
    if (key.isEmpty) {
      return 'Cloud brain set nahi hai. Assistant settings mein Gemini key daalo.';
    }
    final m = await model;
    final useGround = await grounding;
    try {
      final first = await _call(m, key, question, useGround, history);
      if (first.$1 != null) return first.$1!;
      // Grounding rejected by this tier → retry plainly (still a good answer).
      if (useGround && first.$2) {
        final plain = await _call(m, key, question, false, history);
        if (plain.$1 != null) return plain.$1!;
      }
      if (first.$3 != null) AerisLog.add('gemini', first.$3!);
      return first.$3 ?? 'Cloud brain se jawab nahi mila.';
    } catch (e) {
      AerisLog.add('gemini', e);
      return 'Internet ya cloud brain mein dikkat hai: $e';
    }
  }

  /// Continuity: the laptop-synced personal-facts slice (KG triples only —
  /// see docs/CONTINUITY_ARCHITECTURE.md §5c). With it, Tier-3 answers
  /// know the user even when the laptop is off. Empty → plain prompt.
  static Future<String> _systemWithMemory() async {
    try {
      final facts = await Continuity.memoryFacts();
      if (facts.isEmpty) return _system;
      final block = facts.take(25).map((f) => '- $f').join('\n');
      return '$_system\n\nUser ke baare mein yaad rakhi baatein '
          '(naturally use karo, list mat sunao):\n$block';
    } catch (_) {
      return _system;
    }
  }

  /// Returns (answer, groundingRejected, rawError).
  static Future<(String?, bool, String?)> _call(String model, String key,
      String q, bool ground, List<Map<String, String>> history) async {
    final uri = Uri.parse(
        'https://generativelanguage.googleapis.com/v1beta/models/$model:generateContent?key=$key');
    final contents = <Map<String, dynamic>>[
      for (final turn in history)
        {
          'role': turn['role'] == 'model' ? 'model' : 'user',
          'parts': [
            {'text': turn['text'] ?? ''}
          ]
        },
      {
        'role': 'user',
        'parts': [
          {'text': q}
        ]
      },
    ];
    final body = <String, dynamic>{
      'contents': contents,
      'systemInstruction': {
        'parts': [
          {'text': await _systemWithMemory()}
        ]
      },
      'generationConfig': {'temperature': 0.7, 'maxOutputTokens': 400},
      if (ground) 'tools': [
        {'google_search': {}}
      ],
    };
    final r = await http
        .post(uri,
            headers: {'Content-Type': 'application/json'},
            body: jsonEncode(body))
        .timeout(const Duration(seconds: 25));
    if (r.statusCode == 200) {
      final data = jsonDecode(r.body) as Map<String, dynamic>;
      final cands = data['candidates'] as List?;
      if (cands != null && cands.isNotEmpty) {
        final parts =
            (cands.first['content']?['parts'] as List?) ?? const [];
        final text = parts
            .map((p) => (p as Map)['text'] ?? '')
            .join(' ')
            .trim();
        if (text.isNotEmpty) return (text, false, null);
      }
      return (null, false, 'Khaali jawab aaya.');
    }
    // Error — decide if it's a grounding-tier rejection so caller can retry.
    final msg = _errorMessage(r.body);
    final rejected = ground &&
        (r.statusCode == 400 || r.statusCode == 403) &&
        RegExp(r'search|ground|tool', caseSensitive: false).hasMatch(msg);
    return (null, rejected, 'Gemini error ${r.statusCode}: $msg');
  }

  static String _errorMessage(String body) {
    try {
      final d = jsonDecode(body) as Map<String, dynamic>;
      return (d['error']?['message'] ?? body).toString();
    } catch (_) {
      return body;
    }
  }
}
