// Utterance stitching — the rules behind "don't act on half a sentence".
//
// Google's Android recognizer ends a session after ~1-2 s of silence and
// ignores EXTRA_SPEECH_INPUT_COMPLETE_SILENCE_LENGTH_MILLIS, so a natural
// pause mid-command ("Hi Jarvis … ek image banao … aur Ravi ko bhejo") used to
// arrive as three separate commands. ChatScreen now collects each final
// result into one utterance, re-opens the mic at once, and only acts after a
// real gap with no new speech. These pure helpers decide how long that gap
// is; test/utterance_test.dart pins them.
class Utterance {
  Utterance._();

  /// Normal end-of-command gap, counted from when the mic re-opens.
  static const hold = Duration(milliseconds: 1800);

  /// Longer gap when the words so far clearly aren't finished.
  static const holdDangling = Duration(milliseconds: 3200);

  /// Words that can't end a command — the speaker is mid-thought.
  static final _dangling = RegExp(
      r'\b(aur|and|phir|fir|then|ko|ka|ki|ke|se|mein|me|pe|par|to|ya|or|'
      r'the|a|an|of|for|with|uske|iske|baad|jo|kyunki|because|lekin|but|'
      r'matlab|like|um|uh|umm|hmm|please|firstly|pehle|'
      r'jarvis|aeris|hi jarvis|hey jarvis|hi aeris|hey aeris|ok jarvis)$');

  /// Joins a new final result onto what was already heard. Android sometimes
  /// re-sends the previous segment, so exact repeats are dropped.
  static String join(String sofar, String next) {
    final a = sofar.trim(), b = next.trim();
    if (a.isEmpty) return b;
    if (b.isEmpty || a.toLowerCase().endsWith(b.toLowerCase())) return a;
    if (b.toLowerCase().startsWith(a.toLowerCase())) return b;
    return '$a $b';
  }

  /// True when [text] ends mid-thought ("... aur", "Hi Jarvis").
  static bool dangling(String text) =>
      _dangling.hasMatch(text.toLowerCase().trim());

  /// How long to wait for more speech before acting on [text].
  static Duration holdFor(String text) =>
      dangling(text) ? holdDangling : hold;

  static final _instant = RegExp(
      r'^(bye|bye bye|good ?bye|good ?night|khatam|tata|bas|bus|ruko|stop|'
      r'cancel|haan|han|haa|ha|yes|no|nahi|nahin|ok|okay|theek hai)$');

  /// Act at once, without waiting: one-word replies ("haan", "bas", "bye"),
  /// and anything said while a yes/no question is pending.
  static bool commitNow(String text, {bool awaitingYesNo = false}) {
    final s = text.toLowerCase().trim();
    if (s.isEmpty) return false;
    return awaitingYesNo || _instant.hasMatch(s);
  }
}
