import 'package:aeris_mobile/brain/router.dart';
import 'package:aeris_mobile/brain/tier.dart';
import 'package:aeris_mobile/skills/builtin/builtins.dart';
import 'package:aeris_mobile/state/conversation.dart';
import 'package:flutter_test/flutter_test.dart';

BrainRouter build() => BrainRouter(skills: defaultSkills());

void main() {
  group('unit follow-ups', () {
    test('"and in feet?" reuses the previous amount', () async {
      final r = build();
      await r.ask('12 km in miles');

      final a = await r.ask('and in feet?');
      expect(a.tier, Tier.device);
      expect(a.skillName, 'units');
      expect(a.resolvedAs, '12 km in feet');
      expect(a.text, contains('feet'));
    });

    test('a bare unit works too', () async {
      final r = build();
      await r.ask('12 km in miles');
      expect((await r.ask('metres')).resolvedAs, '12 km in metres');
    });

    test('follow-ups chain from the rewritten question', () async {
      final r = build();
      await r.ask('12 km in miles');
      await r.ask('and in feet');
      // The context is now "12 km in feet", so this resolves off that.
      expect((await r.ask('and in inches')).resolvedAs, '12 km in inches');
    });

    test('prose is not mistaken for a unit', () async {
      final r = build();
      await r.ask('12 km in miles');

      final a = await r.ask('and how far is the moon');
      expect(a.resolvedAs, isNull);
      expect(a.tier, Tier.none);
    });
  });

  group('percentage follow-ups', () {
    test('"and 20%?" reuses the previous total', () async {
      final r = build();
      await r.ask('15% of 2400');

      final a = await r.ask('and 20%?');
      expect(a.resolvedAs, '20% of 2400');
      expect(a.text, '480');
    });

    test('works from the Hinglish word order too', () async {
      final r = build();
      await r.ask('2400 ka 15 percent');
      expect((await r.ask('and 20 percent')).text, '480');
    });

    test('a bare number is too ambiguous to act on', () async {
      final r = build();
      await r.ask('15% of 2400');

      final a = await r.ask('and 20');
      expect(a.resolvedAs, isNull);
    });
  });

  group('split follow-ups', () {
    test('"what about 6?" re-splits the same bill', () async {
      final r = build();
      await r.ask('split 2400 between 4');

      final a = await r.ask('what about 6?');
      expect(a.resolvedAs, 'split 2400 between 6');
      expect(a.text, '400 each');
    });

    test('accepts a count with a noun', () async {
      final r = build();
      await r.ask('split 2400 between 4');
      expect((await r.ask('and 8 people')).text, '300 each');
    });
  });

  group('context boundaries', () {
    test('nothing to follow up on at the start', () async {
      final a = await build().ask('and in feet?');
      expect(a.tier, Tier.none);
      expect(a.resolvedAs, isNull);
    });

    test('a follow-up is only offered to the skill that answered', () async {
      final r = build();
      await r.ask('15% of 2400'); // math holds the context
      // A unit-shaped follow-up must not resolve against a maths answer.
      final a = await r.ask('and in feet');
      expect(a.resolvedAs, isNull);
    });

    test('an unrelated question replaces the context', () async {
      final r = build();
      await r.ask('12 km in miles');
      await r.ask('split 2400 between 4');

      // Units no longer holds the context, so this is not a unit follow-up.
      final a = await r.ask('and in feet');
      expect(a.resolvedAs, isNull);
    });

    test('a full question still wins over a follow-up reading', () async {
      final r = build();
      await r.ask('12 km in miles');

      final a = await r.ask('5 kg in pounds');
      expect(a.resolvedAs, isNull, reason: 'it claimed the utterance outright');
      expect(a.text, contains('pounds'));
    });

    test('clearing the transcript forgets the context', () async {
      final skills = defaultSkills();
      final router = BrainRouter(skills: skills);
      final convo = Conversation(router);

      await convo.send('12 km in miles');
      convo.clear();

      final a = await router.ask('and in feet');
      expect(a.resolvedAs, isNull);
      expect(a.tier, Tier.none);
    });
  });
}
