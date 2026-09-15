import '../../core/num_format.dart';
import '../skill.dart';
import '../utterance.dart';
import 'expression.dart';

/// Arithmetic, percentages, and the handful of phrasings people actually use
/// out loud — in English and Hinglish.
class MathSkill extends Skill {
  const MathSkill();

  @override
  String get name => 'math';

  @override
  String get description => 'Arithmetic and percentages, worked out on the phone';

  @override
  List<String> get examples => const [
        '23 * 4 + 7',
        '15% of 2400',
        'what is 18 percent of 950',
        '2400 ka 15 percent',
        '(120 + 80) / 4',
      ];

  static final _percentOf = RegExp(
    r'([\d.,]+)\s*(?:%|percent|per\s*cent|pct)\s*(?:of|ka|ke)?\s*([\d.,]+)',
  );

  // Hinglish: "2400 ka 15 percent" puts the whole before the rate.
  static final _percentOfReversed = RegExp(
    r'([\d.,]+)\s*(?:ka|ke|ki)\s+([\d.,]+)\s*(?:%|percent|per\s*cent|pct)',
  );

  // Double-quoted raw string: the pattern itself contains an apostrophe
  // ("what's"), which a raw single-quoted string cannot hold.
  static final _leadIn = RegExp(
    r"^(?:what(?:'s| is)?|calculate|compute|solve|kitna|kitne|batao|how much(?: is)?)\s+",
  );

  @override
  double score(Utterance u) {
    if (u.isEmpty) return 0;
    final t = _strip(u);

    if (_percentOfReversed.hasMatch(t) || _percentOf.hasMatch(t)) return 0.95;
    if (looksLikeExpression(t)) return 0.9;

    // "what is 45 + 12" — the lead-in was stripped, so re-check.
    if (_leadIn.hasMatch(u.text) && looksLikeExpression(t)) return 0.9;
    return 0;
  }

  /// "15% of 2400" then "and 20%?" -> "20% of 2400".
  @override
  String? followUp(Utterance previous, Utterance current) {
    final prev = previous.text;
    String? whole;

    final reversed = _percentOfReversed.firstMatch(prev);
    if (reversed != null) {
      whole = reversed.group(1);
    } else {
      final forward = _percentOf.firstMatch(prev);
      if (forward != null) whole = forward.group(2);
    }
    if (whole == null) return null;

    final rate = _bareRate(current.text);
    return rate == null ? null : '$rate% of $whole';
  }

  /// The percent sign or the word is required: a bare "and 20" is too
  /// ambiguous to act on silently.
  static String? _bareRate(String s) {
    final t = s
        .replaceFirst(
            RegExp(r'^(?:and|aur|what about|how about|ok|okay)\s+'), '')
        .replaceAll(RegExp(r'[?.!]'), '')
        .trim();
    final m = RegExp(r'^([\d.]+)\s*(?:%|percent|per\s*cent)$').firstMatch(t);
    return m?.group(1);
  }

  @override
  SkillReply run(Utterance u) {
    final t = _strip(u);

    final reversed = _percentOfReversed.firstMatch(t);
    if (reversed != null) {
      final whole = _num(reversed.group(1)!);
      final rate = _num(reversed.group(2)!);
      return _percentReply(rate, whole);
    }

    final forward = _percentOf.firstMatch(t);
    if (forward != null) {
      final rate = _num(forward.group(1)!);
      final whole = _num(forward.group(2)!);
      return _percentReply(rate, whole);
    }

    try {
      final value = evaluateExpression(t);
      return SkillReply(
        groupThousands(formatNumber(value)),
        detail: '${t.trim()} =',
      );
    } on ExprException catch (e) {
      return SkillReply("I couldn't work that out — ${e.message}.");
    }
  }

  SkillReply _percentReply(double rate, double whole) {
    final value = whole * rate / 100;
    return SkillReply(
      groupThousands(formatNumber(value)),
      detail: '${formatNumber(rate)}% of ${groupThousands(formatNumber(whole))} =',
    );
  }

  /// Removes conversational lead-ins and trailing question marks so the parser
  /// only ever sees arithmetic.
  String _strip(Utterance u) {
    var t = u.text.replaceFirst(_leadIn, '');
    t = t.replaceAll(RegExp(r'[?=]+$'), '');
    return t.trim();
  }

  static double _num(String s) => double.parse(s.replaceAll(',', ''));
}
