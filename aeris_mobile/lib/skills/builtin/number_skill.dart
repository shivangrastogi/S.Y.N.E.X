import '../../core/num_format.dart';
import '../skill.dart';
import '../utterance.dart';

/// Lakhs, crores, and numbers in words.
///
/// The rest of the app speaks in thousands and millions because it also does
/// international units. This skill is the one place that works the way the
/// user actually counts — and it is the difference between an assistant that
/// was localised and one that was translated.
class NumberSkill extends Skill {
  const NumberSkill();

  static const int lakh = 100000;
  static const int crore = 10000000;

  @override
  String get name => 'numbers';

  @override
  String get description => 'Lakhs, crores, and numbers written out in words';

  @override
  List<String> get examples => const [
        '1.5 lakh in numbers',
        '2500000 in lakhs',
        '2 crore in numbers',
        '150000 in words',
      ];

  static final _fromScale = RegExp(
    r'([\d.,]+)\s*(lakhs?|lac|lakhon|crores?|karod)',
  );
  static final _toScale = RegExp(
    r'([\d.,]+)\s+(?:in|into|to|me|mein)\s+(lakhs?|lac|crores?)',
  );
  static final _toWords = RegExp(
    r'([\d.,]+)\s+(?:in|into|to)\s+words',
  );

  @override
  double score(Utterance u) {
    final t = u.text;
    if (_toWords.hasMatch(t)) return 0.95;
    if (_toScale.hasMatch(t)) return 0.95;
    // "1.5 lakh in numbers", and also a bare "2 crore" someone wants expanded.
    if (_fromScale.hasMatch(t)) {
      return u.hasAny(const ['number', 'numeric', 'digits', 'figure']) ? 0.95 : 0.8;
    }
    return 0;
  }

  @override
  SkillReply run(Utterance u) {
    final t = u.text;

    final words = _toWords.firstMatch(t);
    if (words != null) {
      final v = _n(words.group(1)!);
      return SkillReply(
        inWords(v),
        detail: groupIndian(formatNumber(v)),
      );
    }

    // Check "in lakhs" before "1.5 lakh", or "2500000 in lakhs" would match
    // the wrong pattern and try to expand a scale that is not there.
    final to = _toScale.firstMatch(t);
    if (to != null) {
      final v = _n(to.group(1)!);
      final isCrore = to.group(2)!.startsWith('crore');
      final unit = isCrore ? crore : lakh;
      final name = isCrore ? 'crore' : 'lakh';
      return SkillReply(
        '${formatNumber(v / unit, maxDecimals: 4)} $name',
        detail: groupIndian(formatNumber(v)),
      );
    }

    final from = _fromScale.firstMatch(t);
    if (from != null) {
      final v = _n(from.group(1)!);
      final word = from.group(2)!;
      final unit = word.startsWith('crore') || word.startsWith('karod')
          ? crore
          : lakh;
      final total = v * unit;
      return SkillReply(
        groupIndian(formatNumber(total)),
        detail: '${formatNumber(v)} $word · ${groupThousands(formatNumber(total))}',
      );
    }

    return const SkillReply("I couldn't find a number to convert.");
  }

  static double _n(String s) => double.parse(s.replaceAll(',', ''));

  // ---- number to words, Indian system ----

  static const _ones = [
    'zero', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight',
    'nine', 'ten', 'eleven', 'twelve', 'thirteen', 'fourteen', 'fifteen',
    'sixteen', 'seventeen', 'eighteen', 'nineteen',
  ];
  static const _tens = [
    '', '', 'twenty', 'thirty', 'forty', 'fifty', 'sixty', 'seventy',
    'eighty', 'ninety',
  ];

  /// Writes [value] out in the Indian system — crore, lakh, thousand — rather
  /// than the short scale's million and billion.
  static String inWords(double value) {
    if (value.isNaN || value.isInfinite) return 'not a number';

    final negative = value < 0;
    final abs = value.abs();
    final whole = abs.truncate();
    final fraction = abs - whole;

    final buf = StringBuffer();
    if (negative) buf.write('minus ');
    buf.write(_whole(whole));

    if (fraction > 1e-9) {
      // Digits are read one by one after "point", as people say them.
      final digits = formatNumber(fraction, maxDecimals: 6);
      final after = digits.contains('.') ? digits.split('.')[1] : '';
      if (after.isNotEmpty) {
        buf.write(' point');
        for (final d in after.split('')) {
          buf.write(' ${_ones[int.parse(d)]}');
        }
      }
    }
    return buf.toString();
  }

  static String _whole(int n) {
    if (n == 0) return 'zero';

    final parts = <String>[];
    var rest = n;

    if (rest >= crore) {
      parts.add('${_whole(rest ~/ crore)} crore');
      rest %= crore;
    }
    if (rest >= lakh) {
      parts.add('${_under100(rest ~/ lakh)} lakh');
      rest %= lakh;
    }
    if (rest >= 1000) {
      parts.add('${_under100(rest ~/ 1000)} thousand');
      rest %= 1000;
    }
    if (rest >= 100) {
      parts.add('${_ones[rest ~/ 100]} hundred');
      rest %= 100;
    }
    if (rest > 0) parts.add(_under100(rest));

    return parts.join(' ');
  }

  static String _under100(int n) {
    if (n < 20) return _ones[n];
    final t = _tens[n ~/ 10];
    final o = n % 10;
    return o == 0 ? t : '$t-${_ones[o]}';
  }
}
