import 'package:aeris_mobile/skills/builtin/builtins.dart';
import 'package:aeris_mobile/skills/builtin/date_parse.dart';
import 'package:aeris_mobile/skills/builtin/date_skill.dart';
import 'package:aeris_mobile/skills/skill.dart';
import 'package:aeris_mobile/skills/utterance.dart';
import 'package:flutter_test/flutter_test.dart';

/// Frozen "now": Tuesday 4 August 2026.
final now = DateTime(2026, 8, 4, 15, 7);
final skill = DateSkill(clock: () => now);

SkillReply ask(String text) => skill.run(Utterance(text));
DateTime? parse(String s) => parseDate(s, now: now);

void main() {
  group('date parsing', () {
    test('reads ISO', () {
      expect(parse('2026-08-15'), DateTime(2026, 8, 15));
    });

    test('reads numeric day-first', () {
      expect(parse('15/8/2026'), DateTime(2026, 8, 15));
      expect(parse('3-4-2026'), DateTime(2026, 4, 3),
          reason: '3 April, not 4 March');
    });

    test('reads month names in either order, with ordinals', () {
      expect(parse('15 august 2026'), DateTime(2026, 8, 15));
      expect(parse('15th aug 2026'), DateTime(2026, 8, 15));
      expect(parse('august 15 2026'), DateTime(2026, 8, 15));
      expect(parse('Dec 25'), DateTime(2026, 12, 25));
    });

    test('fills in the current year when none is given', () {
      expect(parse('25 december'), DateTime(2026, 12, 25));
    });

    test('pivots two-digit years so birth years still work', () {
      expect(parse('12/3/98'), DateTime(1998, 3, 12));
      expect(parse('12/3/26'), DateTime(2026, 3, 12));
    });

    test('understands relative words', () {
      expect(parse('today'), DateTime(2026, 8, 4));
      expect(parse('tomorrow'), DateTime(2026, 8, 5));
      expect(parse('yesterday'), DateTime(2026, 8, 3));
    });

    test('rejects impossible dates rather than rolling them over', () {
      expect(parse('31 february 2026'), isNull, reason: 'would become 3 March');
      expect(parse('32 january 2026'), isNull);
      expect(parse('15/13/2026'), isNull);
    });

    test('returns null for things that are not dates', () {
      expect(parse('hello'), isNull);
      expect(parse(''), isNull);
      expect(parse('15 blorpuary'), isNull);
    });

    test('handles leap years', () {
      expect(parse('29 february 2024'), DateTime(2024, 2, 29));
      expect(parse('29 february 2026'), isNull, reason: '2026 is not a leap year');
    });
  });

  group('daysBetween', () {
    test('counts whole days regardless of time of day', () {
      expect(daysBetween(DateTime(2026, 1, 1, 23), DateTime(2026, 1, 2, 1)), 1);
    });

    test('spans a leap day correctly', () {
      expect(daysBetween(DateTime(2024, 2, 28), DateTime(2024, 3, 1)), 2);
      expect(daysBetween(DateTime(2026, 2, 28), DateTime(2026, 3, 1)), 1);
    });
  });

  group('days between two dates', () {
    test('reports the gap and its length in weeks', () {
      final r = ask('days between 1 jan 2026 and 15 aug 2026');
      expect(r.text, '226 days');
      expect(r.detail, contains('1 January 2026 to 15 August 2026'));
      expect(r.detail, contains('32 weeks 2 days'));
    });

    test('is order-independent', () {
      expect(ask('days between 15 aug 2026 and 1 jan 2026').text, '226 days');
    });

    test('names the part it could not read', () {
      expect(ask('days between blorp and 1 jan 2026').text,
          contains('couldn\'t read "blorp"'));
    });
  });

  group('countdown', () {
    test('counts forward to a date later this year', () {
      final r = ask('how many days until 25 december');
      expect(r.text, '143 days');
      expect(r.detail, contains('Friday, 25 December 2026'));
    });

    test('rolls a bare past date forward to next year', () {
      // 1 January already passed in 2026, so the answer is Jan 2027.
      final r = ask('days until 1 january');
      expect(r.detail, contains('2027'));
    });

    test('respects an explicit year instead of rolling it', () {
      final r = ask('days until 1 january 2026');
      expect(r.text, contains('ago'));
    });

    test('says so when the date is today', () {
      expect(ask('days until 4 august 2026').text, contains('today'));
    });
  });

  group('age', () {
    test('reports years, months, and days', () {
      final r = ask('how old am i if i was born 12 march 1998');
      expect(r.text, '28 years, 4 months, 23 days');
      expect(r.detail, contains('born Thursday, 12 March 1998'));
    });

    test('handles a birthday earlier this month', () {
      expect(ask('how old am i if i was born 1 august 2000').text,
          '26 years, 3 days');
    });

    test('handles an exact birthday with no remainder', () {
      expect(ask('how old am i if i was born 4 august 2000').text, '26 years');
    });

    test('refuses a future birth date', () {
      expect(ask('how old am i if i was born 1 january 2030').text,
          contains('future'));
    });
  });

  group('shifting a date', () {
    test('moves forward', () {
      final r = ask('90 days after 1 march 2026');
      expect(r.text, 'Saturday, 30 May 2026');
    });

    test('moves backward', () {
      final r = ask('30 days before 1 march 2026');
      expect(r.text, 'Friday, 30 January 2026');
    });
  });

  group('routing', () {
    final skills = defaultSkills();

    test('claims its own examples', () {
      for (final example in const DateSkill().examples) {
        expect(skills.select(Utterance(example))?.name, 'dates',
            reason: example);
      }
    });

    test('leaves relative-to-now questions to the time skill', () {
      expect(skills.select(Utterance('what time is it'))?.name, 'time');
      expect(skills.select(Utterance("today's date"))?.name, 'time');
      expect(skills.select(Utterance('what day is it in 45 days'))?.name, 'time');
    });

    test('does not claim spans with no readable date', () {
      expect(skills.select(Utterance('days between meetings')), isNull);
    });
  });
}
