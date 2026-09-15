import 'dart:math';

import '../skill.dart';
import '../utterance.dart';

/// Coin flips, dice, and picking between options.
///
/// Takes its [Random] by injection so a test can assert on an exact outcome
/// instead of asserting "one of these two strings", which passes by luck.
class ChanceSkill extends Skill {
  ChanceSkill({Random? random}) : _random = random ?? Random();

  final Random _random;

  @override
  String get name => 'chance';

  @override
  String get description => 'Coin flips, dice rolls, and random picks';

  @override
  List<String> get examples => const [
        'flip a coin',
        'roll a dice',
        'roll 2d6',
        'pick between chai and coffee',
        'random number between 1 and 100',
      ];

  /// English and Hinglish, in one list so [score] and [run] cannot disagree
  /// about what counts as a dice roll.
  static const _coinWords = [
    'flip a coin',
    'toss a coin',
    'heads or tails',
    'sikka uchalo',
    'sikka uchaal',
    'toss karo',
  ];
  static const _diceWords = [
    'roll a dice',
    'roll a die',
    'roll dice',
    'pasa phenko',
    'pasa fenko',
    'pansa phenko',
  ];

  static final _multiDice = RegExp(r'roll\s+(\d+)\s*d\s*(\d+)');
  static final _between = RegExp(r'(?:pick|choose)\s+(?:between\s+)?(.+?)\s+(?:and|or)\s+(.+)');
  static final _range = RegExp(r'random\s+number\s+between\s+(-?\d+)\s+and\s+(-?\d+)');

  @override
  double score(Utterance u) {
    if (u.hasAny(_coinWords)) {
      return 0.95;
    }
    if (_range.hasMatch(u.text)) return 0.95;
    if (u.hasAny(_diceWords)) return 0.95;
    if (_multiDice.hasMatch(u.text)) return 0.95;
    if (_between.hasMatch(u.text)) return 0.85;
    return 0;
  }

  @override
  SkillReply run(Utterance u) {
    final t = u.text;

    if (u.hasAny(_coinWords)) {
      return SkillReply(_random.nextBool() ? 'Heads' : 'Tails');
    }

    final range = _range.firstMatch(t);
    if (range != null) {
      var lo = int.parse(range.group(1)!);
      var hi = int.parse(range.group(2)!);
      if (lo > hi) {
        final swap = lo;
        lo = hi;
        hi = swap;
      }
      final v = lo + _random.nextInt(hi - lo + 1);
      return SkillReply('$v', detail: 'between $lo and $hi');
    }

    final multi = _multiDice.firstMatch(t);
    if (multi != null) {
      final count = int.parse(multi.group(1)!).clamp(1, 100);
      final sides = int.parse(multi.group(2)!).clamp(2, 1000);
      final rolls = List.generate(count, (_) => 1 + _random.nextInt(sides));
      final total = rolls.reduce((a, b) => a + b);
      return SkillReply(
        '$total',
        detail: count == 1 ? 'd$sides' : '${rolls.join(' + ')} on ${count}d$sides',
      );
    }

    if (u.hasAny(_diceWords)) {
      return SkillReply('${1 + _random.nextInt(6)}', detail: 'd6');
    }

    final between = _between.firstMatch(t);
    if (between != null) {
      final a = between.group(1)!.trim();
      final b = between.group(2)!.trim();
      return SkillReply(_random.nextBool() ? a : b, detail: '$a / $b');
    }

    return const SkillReply("I couldn't tell what to pick from.");
  }
}
