import 'dart:math';

import 'package:aeris_mobile/skills/builtin/builtins.dart';
import 'package:aeris_mobile/skills/builtin/chance_skill.dart';
import 'package:aeris_mobile/skills/builtin/expression.dart';
import 'package:aeris_mobile/skills/builtin/math_skill.dart';
import 'package:aeris_mobile/skills/builtin/text_skill.dart';
import 'package:aeris_mobile/skills/builtin/time_skill.dart';
import 'package:aeris_mobile/skills/builtin/units_skill.dart';
import 'package:aeris_mobile/skills/skill.dart';
import 'package:aeris_mobile/skills/utterance.dart';
import 'package:flutter_test/flutter_test.dart';

Future<String> reply(Skill s, String text) async {
  final r = await s.run(Utterance(text));
  return r.text;
}

void main() {
  group('expression evaluator', () {
    test('respects operator precedence', () {
      expect(evaluateExpression('2 + 3 * 4'), 14);
      expect(evaluateExpression('(2 + 3) * 4'), 20);
    });

    test('exponent is right-associative and binds tighter than unary minus', () {
      expect(evaluateExpression('2^3^2'), 512); // not 64
      expect(evaluateExpression('-2^2'), -4); // not 4
    });

    test('supports x and comma-grouped numbers', () {
      expect(evaluateExpression('12 x 4'), 48);
      expect(evaluateExpression('1,200 + 300'), 1500);
    });

    test('implicit multiplication only before a bracket', () {
      expect(evaluateExpression('3(4+1)'), 15);
      expect(() => evaluateExpression('2 3'), throwsA(isA<ExprException>()));
    });

    test('rejects division by zero rather than returning infinity', () {
      expect(() => evaluateExpression('5/0'), throwsA(isA<ExprException>()));
    });

    test('reports unbalanced brackets', () {
      expect(() => evaluateExpression('(2+3'), throwsA(isA<ExprException>()));
    });

    test('looksLikeExpression ignores prose containing a hyphen', () {
      expect(looksLikeExpression('2 + 2'), isTrue);
      expect(looksLikeExpression('re-run the 2 tests'), isFalse);
      expect(looksLikeExpression('hello'), isFalse);
    });
  });

  group('math skill', () {
    const skill = MathSkill();

    test('answers a bare expression', () async {
      expect(await reply(skill, '23 * 4 + 7'), '99');
    });

    test('strips conversational lead-ins', () async {
      expect(await reply(skill, 'what is 45 + 12'), '57');
      expect(await reply(skill, 'calculate 100 / 8'), '12.5');
    });

    test('handles percent-of in both word orders', () async {
      expect(await reply(skill, '15% of 2400'), '360');
      expect(await reply(skill, 'what is 18 percent of 950'), '171');
      // Hinglish puts the whole first.
      expect(await reply(skill, '2400 ka 15 percent'), '360');
    });

    test('groups thousands in the answer', () async {
      expect(await reply(skill, '25000 * 4'), '100,000');
    });

    test('declines plain conversation', () {
      expect(skill.score(Utterance('how are you doing today')), 0);
      expect(skill.score(Utterance('remind me to call mum')), 0);
    });

    test('explains a bad expression instead of throwing', () async {
      final r = await reply(skill, '5 / 0');
      expect(r, contains('divide by zero'));
    });
  });

  group('units skill', () {
    const skill = UnitsSkill();

    test('converts distance', () async {
      expect(await reply(skill, '12 km in miles'), '7.4565 miles');
    });

    test('converts temperature with the offset applied', () async {
      expect(await reply(skill, '30 c to f'), '86°F');
      expect(await reply(skill, '86 f to c'), '30°C');
      expect(await reply(skill, '300 k to c'), '26.85°C');
    });

    test('converts mass', () async {
      expect(await reply(skill, '2.5 kg in pounds'), '5.5116 pounds');
    });

    test('refuses to cross dimensions', () async {
      final r = await reply(skill, '5 km in kg');
      expect(r, contains("can't convert"));
    });

    test('scores unknown units at zero', () {
      expect(skill.score(Utterance('12 blorps in miles')), 0);
    });
  });

  group('time skill', () {
    // Frozen clock: a Tuesday.
    final skill = TimeSkill(clock: () => DateTime(2026, 8, 4, 15, 7));

    test('reports the clock in 12-hour form', () async {
      expect(await reply(skill, 'what time is it'), '3:07 pm');
    });

    test('answers Hinglish phrasing', () async {
      expect(await reply(skill, 'kya time hua hai'), '3:07 pm');
    });

    test("gives today's date with the weekday", () async {
      expect(await reply(skill, "today's date"), 'Tuesday, 4 August 2026');
    });

    test('does day arithmetic', () async {
      // 4 Aug 2026 is a Tuesday; +45 days crosses into September and lands
      // three weekdays on, so Friday 18 September.
      expect(await reply(skill, 'what day is it in 45 days'),
          'Friday, 18 September 2026');
    });
  });

  group('text skill', () {
    const skill = TextSkill();

    test('reverses, preserving original casing', () async {
      expect(await reply(skill, 'reverse Stressed'), 'dessertS');
    });

    test('counts words and characters', () async {
      expect(await reply(skill, 'count words in the quick brown fox'), '4 words');
      expect(await reply(skill, 'how many characters in hello world'),
          '10 characters');
    });

    test('re-cases', () async {
      expect(await reply(skill, 'uppercase hello world'), 'HELLO WORLD');
    });
  });

  group('chance skill', () {
    test('is deterministic under a seeded Random', () async {
      final skill = ChanceSkill(random: Random(7));
      final flip = await reply(skill, 'flip a coin');
      expect(flip, anyOf('Heads', 'Tails'));

      // Same seed, same sequence — proves the injection actually takes effect.
      final a = await reply(ChanceSkill(random: Random(1)), 'roll a dice');
      final b = await reply(ChanceSkill(random: Random(1)), 'roll a dice');
      expect(a, b);
    });

    test('stays inside the requested range', () async {
      for (var seed = 0; seed < 25; seed++) {
        final skill = ChanceSkill(random: Random(seed));
        final v = int.parse(await reply(skill, 'random number between 1 and 6'));
        expect(v, inInclusiveRange(1, 6));
      }
    });

    test('sums multiple dice', () async {
      final skill = ChanceSkill(random: Random(3));
      final total = int.parse(await reply(skill, 'roll 2d6'));
      expect(total, inInclusiveRange(2, 12));
    });
  });

  group('registry', () {
    final skills = defaultSkills();

    test('routes each example to the skill that owns it', () {
      for (final skill in skills.all) {
        for (final example in skill.examples) {
          expect(
            skills.select(Utterance(example))?.name,
            skill.name,
            reason: '"$example" should route to ${skill.name}',
          );
        }
      }
    });

    test('declines what belongs to the laptop', () {
      const offDevice = [
        'open spotify',
        'what is on my calendar tomorrow',
        'send a whatsapp to rahul',
        'summarise my last email',
        'how are you',
      ];
      for (final text in offDevice) {
        expect(skills.select(Utterance(text)), isNull, reason: text);
      }
    });

    test('an empty utterance selects nothing', () {
      expect(skills.select(Utterance('   ')), isNull);
    });
  });
}
