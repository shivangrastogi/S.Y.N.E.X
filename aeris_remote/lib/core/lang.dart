// Conversation language. Hinglish is the original, hand-tuned stack (Google
// en-IN STT + Hinglish replies) and stays the default; English mode is a
// separate switch on top of it — nothing Hinglish is removed.
//
//   hinglish   en-IN STT, en-IN TTS, Hinglish replies
//   englishIn  en-IN STT (Indian accent), en-IN TTS, English-only replies
//   englishUs  en-US STT, en-US TTS, English-only replies
//
// Every user-facing reply goes through Lang.t(hinglish, english), so the
// two wordings sit side by side at each call site.
import 'package:flutter/foundation.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

enum LangMode { hinglish, englishIn, englishUs }

class Lang {
  Lang._();
  static const _store = FlutterSecureStorage();
  static const _kMode = 'voice_lang';

  /// Current mode; listen to rebuild UI when it changes.
  static final ValueNotifier<LangMode> mode =
      ValueNotifier<LangMode>(LangMode.hinglish);

  static bool get english => mode.value != LangMode.hinglish;

  /// Speech-to-text locale for speech_to_text.
  static String get sttLocale =>
      mode.value == LangMode.englishUs ? 'en_US' : 'en_IN';

  /// Text-to-speech language for flutter_tts.
  static String get ttsLanguage =>
      mode.value == LangMode.englishUs ? 'en-US' : 'en-IN';

  /// Name of the reply language, for LLM prompts.
  static String get replyLanguage =>
      english ? 'simple English (no Hindi words at all)' : 'Hinglish';

  /// Pick the wording for the current mode.
  static String t(String hinglish, String english) =>
      Lang.english ? english : hinglish;

  static Future<void> load() async {
    try {
      final v = await _store.read(key: _kMode);
      mode.value = LangMode.values.firstWhere((m) => m.name == v,
          orElse: () => LangMode.hinglish);
    } catch (_) {}
  }

  static Future<void> set(LangMode m) async {
    mode.value = m;
    try {
      await _store.write(key: _kMode, value: m.name);
    } catch (_) {}
  }
}
