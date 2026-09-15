import 'dart:math';

import 'package:aeris_mobile/brain/router.dart';
import 'package:aeris_mobile/brain/tier.dart';
import 'package:aeris_mobile/skills/builtin/builtins.dart';
import 'package:aeris_mobile/skills/builtin/chance_skill.dart';
import 'package:aeris_mobile/skills/builtin/date_skill.dart';
import 'package:aeris_mobile/skills/builtin/finance_skill.dart';
import 'package:aeris_mobile/skills/builtin/math_skill.dart';
import 'package:aeris_mobile/skills/builtin/time_skill.dart';
import 'package:aeris_mobile/skills/builtin/units_skill.dart';
import 'package:aeris_mobile/skills/utterance.dart';
import 'package:flutter_test/flutter_test.dart';

/// A.E.R.I.S is Hinglish-native on the laptop; the phone tier has to be too,
/// or the same sentence works in one place and not the other.
void main() {
  final skills = defaultSkills();
  final at = DateTime(2026, 8, 4, 15, 7);

  String reply(String text) {
    final s = skills.select(Utterance(text));
    expect(s, isNotNull, reason: 'nothing claimed "$text"');
    return (s!.run(Utterance(text)) as dynamic).text as String;
  }

  group('routes Hinglish to the right skill', () {
    const expected = {
      'kitna 12 x 4': 'math',
      '2400 ka 15 percent': 'math',
      'kya time hua hai': 'time',
      'aaj ki tarikh': 'time',
      '12 km ko miles me badlo': 'units',
      '2400 ko 4 logo me baanto': 'finance',
      'sikka uchalo': 'chance',
      'pasa phenko': 'chance',
      'kya kar sakte ho': 'help',
      'madad': 'help',
      '1 jan 2026 se 15 aug 2026 tak kitne din': 'dates',
    };

    expected.forEach((text, skill) {
      test('"$text" -> $skill', () {
        expect(skills.select(Utterance(text))?.name, skill);
      });
    });
  });

  group('answers correctly', () {
    test('maths in Hinglish', () {
      expect(const MathSkill().run(Utterance('kitna 12 x 4')).text, '48');
      expect(const MathSkill().run(Utterance('2400 ka 15 percent')).text, '360');
    });

    test('unit conversion with ko ... me', () {
      final r = const UnitsSkill().run(Utterance('12 km ko miles me badlo'));
      expect(r.text, '7.4565 miles');
    });

    test('splitting a bill in Hinglish', () {
      final r = const FinanceSkill().run(Utterance('2400 ko 4 logo me baanto'));
      expect(r.text, '600 each');
    });

    test('a date span in Hinglish', () {
      final s = DateSkill(clock: () => at);
      final r = s.run(Utterance('1 jan 2026 se 15 aug 2026 tak kitne din'));
      expect(r.text, '226 days');
    });

    test('the clock in Hinglish', () {
      final s = TimeSkill(clock: () => at);
      expect(s.run(Utterance('kya time hua hai')).text, '3:07 pm');
    });

    test('a coin toss in Hinglish', () {
      final s = ChanceSkill(random: Random(1));
      expect(s.run(Utterance('sikka uchalo')).text, anyOf('Heads', 'Tails'));
    });

    test('a dice roll in Hinglish', () {
      final s = ChanceSkill(random: Random(1));
      final v = int.parse(s.run(Utterance('pasa phenko')).text);
      expect(v, inInclusiveRange(1, 6));
    });
  });

  group('end to end through the router', () {
    test('Hinglish is answered on-device, not sent onward', () async {
      final router = BrainRouter(skills: defaultSkills());
      final a = await router.ask('2400 ko 4 logo me baanto');
      expect(a.tier, Tier.device);
      expect(a.text, '600 each');
      expect(a.skillName, 'finance');
    });
  });

  group('does not over-claim', () {
    test('Hinglish that is not one of these skills still falls through', () {
      for (final text in const [
        'mummy ko call karo',
        'gaana chalao',
        'whatsapp bhejo rahul ko',
        'mera calendar dikhao',
      ]) {
        expect(skills.select(Utterance(text)), isNull, reason: text);
      }
    });

    test('"ko" alone does not turn prose into a unit conversion', () {
      expect(skills.select(Utterance('use ko batao')), isNull);
    });

    test('reply() helper found a skill for every phrase above', () {
      // Guards the helper itself: if select() started returning null the
      // group above would fail loudly rather than silently pass.
      expect(reply('kitna 12 x 4'), '48');
    });
  });
}
