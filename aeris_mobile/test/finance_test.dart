import 'package:aeris_mobile/skills/builtin/builtins.dart';
import 'package:aeris_mobile/skills/builtin/finance_skill.dart';
import 'package:aeris_mobile/skills/skill.dart';
import 'package:aeris_mobile/skills/utterance.dart';
import 'package:flutter_test/flutter_test.dart';

// FinanceSkill.run is synchronous, so these read straight through.
SkillReply ask(String text) => const FinanceSkill().run(Utterance(text));

void main() {
  group('splitting a bill', () {
    test('divides evenly', () async {
      expect((ask('split 2400 between 4')).text, '600 each');
    });

    test('accepts by/among as well as between', () async {
      expect((ask('split 900 by 3')).text, '300 each');
      expect((ask('split 1000 among 8')).text, '125 each');
    });

    test('keeps two decimals when it does not divide cleanly', () async {
      expect((ask('split 100 between 3')).text, '33.33 each');
    });

    test('adds a tip before splitting', () async {
      final r = ask('split 2000 between 4 with 10% tip');
      expect(r.text, '550 each');
      expect(r.detail, contains('2,200'));
    });
  });

  group('tips', () {
    test('uses the stated rate', () async {
      final r = ask('15% tip on 1850');
      expect(r.text, '277.5 tip, 2,127.5 total');
    });

    test('assumes 10% when no rate is given, and says so', () async {
      final r = ask('tip on 500');
      expect(r.text, '50 tip, 550 total');
      expect(r.detail, contains('assuming 10%'));
    });
  });

  group('discounts and tax', () {
    test('takes a percentage off and reports the saving', () async {
      final r = ask('20% off 1500');
      expect(r.text, '1,200');
      expect(r.detail, contains('saves 300'));
    });

    test('adds tax', () async {
      final r = ask('add 18% gst to 2400');
      expect(r.text, '2,832');
      expect(r.detail, contains('432'));
    });

    test('removes tax by dividing, not subtracting', () async {
      // The common mistake is 2832 - 18% = 2322.24. The right answer is
      // 2832 / 1.18 = 2400.
      expect((ask('remove 18% gst from 2832')).text, '2,400');
    });
  });

  group('percentage change', () {
    test('reports direction and magnitude', () async {
      expect((ask('percentage change from 1200 to 1500')).text, 'up 25%');
      expect((ask('percent change from 1500 to 1200')).text, 'down 20%');
    });

    test('refuses to divide by a zero base', () async {
      final r = ask('percentage change from 0 to 500');
      expect(r.text, contains('undefined'));
    });
  });

  group('EMI', () {
    test('computes the monthly payment for a normal loan', () async {
      // 500000 at 9% over 60 months -> 10,379.18 by the standard formula.
      final r = ask('emi on 500000 at 9% for 5 years');
      expect(r.text, '10,379.18 per month');
      expect(r.detail, contains('60 months'));
      expect(r.detail, contains('interest'));
    });

    test('accepts a term in months', () async {
      final r = ask('emi on 100000 at 12% for 24 months');
      expect(r.text, '4,707.35 per month');
    });

    test('handles a zero-interest loan without dividing by zero', () async {
      final r = ask('emi on 120000 at 0% for 12 months');
      expect(r.text, '10,000 per month');
    });
  });

  group('routing', () {
    final skills = defaultSkills();

    test('finance claims its own phrasings', () {
      const mine = [
        'split 2400 between 4',
        '15% tip on 1850',
        '20% off 1500',
        'add 18% gst to 2400',
        'emi on 500000 at 9% for 5 years',
      ];
      for (final text in mine) {
        expect(skills.select(Utterance(text))?.name, 'finance', reason: text);
      }
    });

    test('does not steal plain arithmetic from the maths skill', () {
      expect(skills.select(Utterance('23 * 4 + 7'))?.name, 'math');
      expect(skills.select(Utterance('15% of 2400'))?.name, 'math');
    });

    test('does not steal unit conversion', () {
      // "12 km in miles" contains no percent or money verb; units must win.
      expect(skills.select(Utterance('12 km in miles'))?.name, 'units');
    });

    test('leaves bare "from X to Y" to the other skills', () {
      // No "percent"/"change" wording, so finance must not claim it.
      expect(skills.select(Utterance('30 c to f'))?.name, 'units');
    });
  });
}
