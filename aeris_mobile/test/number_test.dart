import 'package:aeris_mobile/core/num_format.dart';
import 'package:aeris_mobile/skills/builtin/builtins.dart';
import 'package:aeris_mobile/skills/builtin/number_skill.dart';
import 'package:aeris_mobile/skills/skill.dart';
import 'package:aeris_mobile/skills/utterance.dart';
import 'package:flutter_test/flutter_test.dart';

SkillReply ask(String text) => const NumberSkill().run(Utterance(text));

void main() {
  group('Indian grouping', () {
    test('groups the last three, then pairs', () {
      expect(groupIndian('1234567'), '12,34,567');
      expect(groupIndian('150000'), '1,50,000');
      expect(groupIndian('100000000'), '10,00,00,000');
    });

    test('leaves short numbers alone', () {
      expect(groupIndian('999'), '999');
      expect(groupIndian('1000'), '1,000');
    });

    test('keeps the sign and the decimal tail outside the grouping', () {
      expect(groupIndian('-1234567'), '-12,34,567');
      expect(groupIndian('1234567.25'), '12,34,567.25');
    });

    test('is not the same as thousands grouping', () {
      expect(groupThousands('1234567'), '1,234,567');
      expect(groupIndian('1234567'), '12,34,567');
    });
  });

  group('expanding a scale', () {
    test('lakh', () {
      final r = ask('1.5 lakh in numbers');
      expect(r.text, '1,50,000');
      expect(r.detail, contains('150,000'));
    });

    test('crore', () {
      expect(ask('2 crore in numbers').text, '2,00,00,000');
    });

    test('Hinglish spellings', () {
      expect(ask('3 lac in numbers').text, '3,00,000');
      expect(ask('1 karod in numbers').text, '1,00,00,000');
    });
  });

  group('reducing to a scale', () {
    test('to lakhs', () {
      final r = ask('2500000 in lakhs');
      expect(r.text, '25 lakh');
      expect(r.detail, '25,00,000');
    });

    test('to crores', () {
      expect(ask('50000000 in crores').text, '5 crore');
    });

    test('keeps a fractional part', () {
      expect(ask('150000 in lakhs').text, '1.5 lakh');
    });
  });

  group('numbers in words', () {
    test('uses the Indian system, not millions', () {
      expect(ask('150000 in words').text, 'one lakh fifty thousand');
      expect(ask('2500000 in words').text, 'twenty-five lakh');
      expect(ask('10000000 in words').text, 'one crore');
    });

    test('handles the awkward middles', () {
      expect(NumberSkill.inWords(0), 'zero');
      expect(NumberSkill.inWords(19), 'nineteen');
      expect(NumberSkill.inWords(20), 'twenty');
      expect(NumberSkill.inWords(21), 'twenty-one');
      expect(NumberSkill.inWords(100), 'one hundred');
      expect(NumberSkill.inWords(101), 'one hundred one');
      expect(NumberSkill.inWords(999), 'nine hundred ninety-nine');
    });

    test('composes all four scales', () {
      expect(
        NumberSkill.inWords(12345678),
        'one crore twenty-three lakh forty-five thousand six hundred '
        'seventy-eight',
      );
    });

    test('reads decimals digit by digit', () {
      expect(NumberSkill.inWords(2.5), 'two point five');
      expect(NumberSkill.inWords(1.25), 'one point two five');
    });

    test('handles negatives', () {
      expect(NumberSkill.inWords(-42), 'minus forty-two');
    });
  });

  group('routing', () {
    final skills = defaultSkills();

    test('claims its own examples', () {
      for (final example in const NumberSkill().examples) {
        expect(skills.select(Utterance(example))?.name, 'numbers',
            reason: example);
      }
    });

    test('does not steal unit conversion or plain arithmetic', () {
      expect(skills.select(Utterance('12 km in miles'))?.name, 'units');
      expect(skills.select(Utterance('23 * 4 + 7'))?.name, 'math');
      expect(skills.select(Utterance('15% of 2400'))?.name, 'math');
    });

    test('does not fire on numberless prose', () {
      expect(skills.select(Utterance('tell me about lakhs')), isNull);
    });
  });
}
