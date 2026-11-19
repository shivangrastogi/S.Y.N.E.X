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
import '../core/aeris_log.dart';
import '../laptop/continuity.dart';
import '../core/lang.dart';

class CloudBrain {
  static const _kKey = 'gemini_api_key';
  static const _kModel = 'gemini_model';
  static const _kGround = 'gemini_grounding';
  static const _defaultModel = 'gemini-2.5-flash';
  static const _store = FlutterSecureStorage();

  // Spoken-first, Hinglish — matches the user's voice stack. Short answers,
  // because they get read aloud by TTS.
  static const _systemHinglish =
      'Tum AERIS ho, ek helpful voice assistant. Hinglish (Roman Hindi + '
      'English) mein jawab do, jaise ek dost baat karta hai. Jawab CHOTA aur '
      'seedha rakho — 1 se 3 lines, kyunki ye bol kar sunaya jayega. Lists, '
      'markdown ya symbols mat use karo, saaf bolne wale vaakya likho. Agar '
      'pakka nahi pata to keh do.';
  // English mode (lang.dart): same persona, English only.
  static const _systemEnglish =
      'You are AERIS, a helpful voice assistant. Reply ONLY in simple, '
      'natural English — never use Hindi or Hinglish words, even if the user '
      'does. Keep answers SHORT and direct, 1 to 3 sentences, because they '
      'are read aloud. No lists, markdown or symbols; write plain spoken '
      'sentences. If you are not sure, say so.';
  static String get _system => Lang.t(_systemHinglish, _systemEnglish);

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
      return Lang.t(
          'Cloud brain set nahi hai. Assistant settings mein Gemini key daalo.',
          'The cloud brain isn\'t set up. Add a Gemini key in Assistant settings.');
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
      return first.$3 ??
          Lang.t('Cloud brain se jawab nahi mila.', 'No answer from the cloud brain.');
    } catch (e) {
      AerisLog.add('gemini', e);
      return Lang.t('Internet ya cloud brain mein dikkat hai: $e',
          'There\'s a problem with the internet or the cloud brain: $e');
    }
  }

  /// Settings "Test connection": tries [key]/[model] WITHOUT saving them,
  /// so a bad key can be fixed before it replaces a working one.
  /// Returns (ok, message, milliseconds).
  static Future<(bool, String, int)> test(String key, String model, {bool ground = false}) async {
    final sw = Stopwatch()..start();
    if (key.trim().isEmpty) return (false, 'Enter an API key first', 0);
    try {
      var r = await _call(model.trim().isEmpty ? _defaultModel : model.trim(), key.trim(),
          'Reply with exactly: OK', ground, const []);
      if (r.$1 == null && ground && r.$2) {
        r = await _call(model.trim().isEmpty ? _defaultModel : model.trim(), key.trim(),
            'Reply with exactly: OK', false, const []);
      }
      return r.$1 != null
          ? (true, 'Works', sw.elapsedMilliseconds)
          : (false, r.$3 ?? 'No answer', sw.elapsedMilliseconds);
    } catch (e) {
      return (false, '$e', sw.elapsedMilliseconds);
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
      if (Lang.english) {
        return '$_system\n\nThings you remember about the user (use them '
            'naturally, don\'t list them):\n$block';
      }
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

  /// Phase 10 (agent): one structured call — [system] + [prompt] in, a JSON
  /// object out (Gemini JSON mode). Retries once on rate-limit / overload.
  /// Throws a short message on failure.
  static Future<Map<String, dynamic>> json(String system, String prompt,
      {double temperature = 0.2}) async {
    final key = await apiKey;
    if (key.isEmpty) throw 'Gemini key set nahi hai';
    final m = await model;
    final uri = Uri.parse(
        'https://generativelanguage.googleapis.com/v1beta/models/$m:generateContent?key=$key');
    final body = jsonEncode({
      'contents': [
        {
          'role': 'user',
          'parts': [
            {'text': prompt}
          ]
        }
      ],
      'systemInstruction': {
        'parts': [
          {'text': system}
        ]
      },
      'generationConfig': {
        'temperature': temperature,
        'maxOutputTokens': 2048,
        'responseMimeType': 'application/json',
        // Each agent step is small; thinking would add seconds per tap.
        // Only 2.5 Flash accepts a zero budget.
        if (m.contains('2.5-flash')) 'thinkingConfig': {'thinkingBudget': 0},
      },
    });
    for (var attempt = 0;; attempt++) {
      final r = await http
          .post(uri, headers: {'Content-Type': 'application/json'}, body: body)
          .timeout(const Duration(seconds: 30));
      if (r.statusCode == 200) {
        final data = jsonDecode(r.body) as Map<String, dynamic>;
        final parts = ((data['candidates'] as List?)?.firstOrNull?['content']
                ?['parts'] as List?) ??
            const [];
        final text =
            parts.map((p) => (p as Map)['text'] ?? '').join().trim();
        return parseJsonObject(text);
      }
      if ((r.statusCode == 429 || r.statusCode == 503) && attempt == 0) {
        await Future.delayed(const Duration(seconds: 3));
        continue;
      }
      throw 'Gemini error ${r.statusCode}: ${_errorMessage(r.body)}';
    }
  }

  /// Lenient JSON-object parse: tolerates ```json fences and stray prose
  /// around the object. Throws if no object can be read.
  static Map<String, dynamic> parseJsonObject(String text) {
    final start = text.indexOf('{'), end = text.lastIndexOf('}');
    if (start < 0 || end <= start) throw 'JSON nahi mila: $text';
    final v = jsonDecode(text.substring(start, end + 1));
    if (v is! Map<String, dynamic>) throw 'JSON object nahi hai';
    return v;
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
