/// One thing the user said, normalised once so every skill scores against the
/// same string instead of each rolling its own `toLowerCase().trim()`.
class Utterance {
  Utterance(this.raw)
      : text = _normalise(raw),
        tokens = _normalise(raw).split(' ').where((t) => t.isNotEmpty).toList();

  /// Exactly what the user typed or said.
  final String raw;

  /// Lowercased, punctuation-trimmed, whitespace-collapsed.
  final String text;

  final List<String> tokens;

  bool get isEmpty => text.isEmpty;

  /// True when any of [needles] appears as a substring.
  bool hasAny(Iterable<String> needles) =>
      needles.any((n) => text.contains(n));

  /// True when any of [needles] appears as a whole word — stops "sum" from
  /// firing on "assume".
  bool hasWord(Iterable<String> needles) {
    final set = needles.toSet();
    return tokens.any(set.contains);
  }

  /// Text with a leading trigger phrase removed, e.g. "reverse hello" -> "hello".
  /// Operates on [raw] so the result keeps the user's original casing.
  String after(String trigger) {
    final i = raw.toLowerCase().indexOf(trigger.toLowerCase());
    if (i < 0) return raw.trim();
    return raw.substring(i + trigger.length).trim();
  }

  static String _normalise(String s) {
    final lowered = s.toLowerCase().trim();
    final collapsed = lowered.replaceAll(RegExp(r'\s+'), ' ');
    // Strip sentence-ending punctuation, but keep characters that carry
    // meaning inside an expression: % . , ( ) + - * / ^
    return collapsed.replaceAll(RegExp(r'[?!;:]+$'), '').trim();
  }

  @override
  String toString() => 'Utterance("$text")';
}
