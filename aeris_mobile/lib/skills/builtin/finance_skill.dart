import 'dart:math' as math;

import '../../core/num_format.dart';
import '../skill.dart';
import '../utterance.dart';

/// The money arithmetic people actually do standing in a shop or splitting a
/// bill: tips, splits, discounts, tax, percentage change, and loan EMIs.
///
/// No currency symbol in the answers on purpose — the same number means rupees
/// at dinner and dollars online, and guessing wrong is worse than staying quiet.
class FinanceSkill extends Skill {
  const FinanceSkill();

  @override
  String get name => 'finance';

  @override
  String get description => 'Tips, splits, discounts, tax, and loan EMIs';

  @override
  List<String> get examples => const [
        'split 2400 between 4',
        '15% tip on 1850',
        '20% off 1500',
        'add 18% gst to 2400',
        'emi on 500000 at 9% for 5 years',
      ];

  // ---- patterns, ordered most specific first ----

  static final _splitWithTip = RegExp(
    r'split\s+([\d.,]+)\s+(?:between|among|by|amongst)\s+(\d+)'
    r'.*?(?:with\s+)?([\d.]+)\s*%\s*tip',
  );
  static final _split = RegExp(
    r'split\s+([\d.,]+)\s+(?:between|among|by|amongst)\s+(\d+)',
  );
  /// Hinglish word order puts the amount first and the verb last:
  /// "2400 ko 4 logo me baanto".
  static final _splitHinglish = RegExp(
    r'([\d.,]+)\s+(?:ko|ka)\s+(\d+)\s*(?:logo?n?|log|people)?\s*(?:me|mein)?\s*'
    r'(?:baant|bant)',
  );
  static final _tip = RegExp(
    r'([\d.]+)\s*%?\s*tip\s+(?:on|for)\s+([\d.,]+)',
  );
  static final _tipPlain = RegExp(r'tip\s+(?:on|for)\s+([\d.,]+)');
  static final _discount = RegExp(
    r'([\d.]+)\s*%\s*(?:off|discount\s+on|off\s+of)\s+([\d.,]+)',
  );
  static final _addTax = RegExp(
    r'add\s+([\d.]+)\s*%\s*(?:gst|tax|vat)?\s*(?:to|on)\s+([\d.,]+)',
  );
  static final _removeTax = RegExp(
    r'remove\s+([\d.]+)\s*%\s*(?:gst|tax|vat)\s+(?:from|of)\s+([\d.,]+)',
  );
  static final _change = RegExp(
    r'(?:percent(?:age)?\s+change\s+)?from\s+([\d.,]+)\s+to\s+([\d.,]+)',
  );
  static final _emi = RegExp(
    r'(?:emi|loan|instal?ments?)\s+(?:on|of|for)\s+([\d.,]+)\s+at\s+([\d.]+)\s*%'
    r'\s+for\s+([\d.]+)\s*(years?|months?|saal|mahine)',
  );

  @override
  double score(Utterance u) {
    final t = u.text;
    if (_emi.hasMatch(t)) return 0.96;
    if (_splitWithTip.hasMatch(t) ||
        _split.hasMatch(t) ||
        _splitHinglish.hasMatch(t)) {
      return 0.95;
    }
    if (_removeTax.hasMatch(t) || _addTax.hasMatch(t)) return 0.95;
    if (_discount.hasMatch(t)) return 0.95;
    if (_tip.hasMatch(t) || _tipPlain.hasMatch(t)) return 0.94;
    // "from 1200 to 1500" alone is ambiguous with unit conversion, so only
    // claim it when the utterance actually says it wants a percentage.
    if (_change.hasMatch(t) && u.hasAny(const ['percent', '%', 'change'])) {
      return 0.9;
    }
    return 0;
  }

  /// "split 2400 between 4" then "what about 6?" -> "split 2400 between 6".
  @override
  String? followUp(Utterance previous, Utterance current) {
    final prev = _splitWithTip.firstMatch(previous.text) ??
        _split.firstMatch(previous.text) ??
        _splitHinglish.firstMatch(previous.text);
    if (prev == null) return null;

    final count = _bareCount(current.text);
    return count == null ? null : 'split ${prev.group(1)} between $count';
  }

  static String? _bareCount(String s) {
    final t = s
        .replaceFirst(
            RegExp(r'^(?:and|aur|what about|how about|ok|okay)\s+'), '')
        .replaceAll(RegExp(r'[?.!]'), '')
        .trim();
    final m = RegExp(r'^(\d+)\s*(?:people|persons?|logon?|log)?$').firstMatch(t);
    return m?.group(1);
  }

  @override
  SkillReply run(Utterance u) {
    final t = u.text;

    final emi = _emi.firstMatch(t);
    if (emi != null) return _emiReply(emi);

    final splitTip = _splitWithTip.firstMatch(t);
    if (splitTip != null) {
      final bill = _n(splitTip.group(1)!);
      final people = int.parse(splitTip.group(2)!);
      final rate = double.parse(splitTip.group(3)!);
      if (people <= 0) return const SkillReply('Split between how many people?');
      final total = bill * (1 + rate / 100);
      return SkillReply(
        '${_m(total / people)} each',
        detail: '${_m(bill)} + ${formatNumber(rate)}% tip = ${_m(total)}, '
            'split $people ways',
      );
    }

    final split = _split.firstMatch(t) ?? _splitHinglish.firstMatch(t);
    if (split != null) {
      final bill = _n(split.group(1)!);
      final people = int.parse(split.group(2)!);
      if (people <= 0) return const SkillReply('Split between how many people?');
      return SkillReply(
        '${_m(bill / people)} each',
        detail: '${_m(bill)} split $people ways',
      );
    }

    final removeTax = _removeTax.firstMatch(t);
    if (removeTax != null) {
      final rate = double.parse(removeTax.group(1)!);
      final gross = _n(removeTax.group(2)!);
      final base = gross / (1 + rate / 100);
      return SkillReply(
        _m(base),
        detail: '${_m(gross)} less ${formatNumber(rate)}% tax '
            '(${_m(gross - base)})',
      );
    }

    final addTax = _addTax.firstMatch(t);
    if (addTax != null) {
      final rate = double.parse(addTax.group(1)!);
      final base = _n(addTax.group(2)!);
      final tax = base * rate / 100;
      return SkillReply(
        _m(base + tax),
        detail: '${_m(base)} + ${formatNumber(rate)}% (${_m(tax)})',
      );
    }

    final discount = _discount.firstMatch(t);
    if (discount != null) {
      final rate = double.parse(discount.group(1)!);
      final price = _n(discount.group(2)!);
      final off = price * rate / 100;
      return SkillReply(
        _m(price - off),
        detail: 'saves ${_m(off)} on ${_m(price)}',
      );
    }

    final tip = _tip.firstMatch(t) ?? _tipPlain.firstMatch(t);
    if (tip != null) {
      // _tipPlain has one group (the bill); _tip has rate then bill.
      final hasRate = tip.groupCount >= 2;
      final rate = hasRate ? double.parse(tip.group(1)!) : 10.0;
      final bill = _n(tip.group(hasRate ? 2 : 1)!);
      final amount = bill * rate / 100;
      return SkillReply(
        '${_m(amount)} tip, ${_m(bill + amount)} total',
        detail: '${formatNumber(rate)}% of ${_m(bill)}'
            '${hasRate ? '' : ' (assuming 10%)'}',
      );
    }

    final change = _change.firstMatch(t);
    if (change != null) {
      final from = _n(change.group(1)!);
      final to = _n(change.group(2)!);
      if (from == 0) {
        return const SkillReply(
          'A change from zero has no percentage — it is undefined.',
        );
      }
      final pct = (to - from) / from * 100;
      final dir = pct >= 0 ? 'up' : 'down';
      return SkillReply(
        '$dir ${formatNumber(pct.abs(), maxDecimals: 2)}%',
        detail: '${_m(from)} to ${_m(to)}',
      );
    }

    return const SkillReply("I couldn't work out what to calculate there.");
  }

  SkillReply _emiReply(RegExpMatch m) {
    final principal = _n(m.group(1)!);
    final annualRate = double.parse(m.group(2)!);
    final term = double.parse(m.group(3)!);
    final unit = m.group(4)!;
    final months = unit.startsWith('month') || unit.startsWith('mahine')
        ? term.round()
        : (term * 12).round();

    if (months <= 0) return const SkillReply('Over how long?');

    final r = annualRate / 12 / 100;
    // A zero-interest loan is just the principal spread evenly; the standard
    // formula divides by zero there.
    final emi = r == 0
        ? principal / months
        : principal * r * math.pow(1 + r, months) /
            (math.pow(1 + r, months) - 1);

    final total = emi * months;
    return SkillReply(
      '${_m(emi)} per month',
      detail: '${_m(principal)} at ${formatNumber(annualRate)}% over $months '
          'months · total ${_m(total)}, interest ${_m(total - principal)}',
    );
  }

  static double _n(String s) => double.parse(s.replaceAll(',', ''));

  /// Money: two decimals unless the value is whole, always grouped.
  static String _m(double v) => groupThousands(formatNumber(v, maxDecimals: 2));
}
