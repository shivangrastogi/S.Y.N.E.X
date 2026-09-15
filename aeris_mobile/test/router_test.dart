import 'package:aeris_mobile/brain/router.dart';
import 'package:aeris_mobile/brain/tier.dart';
import 'package:aeris_mobile/skills/builtin/builtins.dart';
import 'package:aeris_mobile/skills/skill.dart';
import 'package:aeris_mobile/skills/utterance.dart';
import 'package:flutter_test/flutter_test.dart';

/// A stand-in remote tier whose reachability and answer are both controllable.
class FakeTier implements TierHandler {
  FakeTier(this.tier, {this.available = true, this.answer, this.throws = false});

  @override
  final Tier tier;
  final bool available;
  final String? answer;
  final bool throws;

  int calls = 0;

  @override
  bool get isAvailable => available;

  @override
  Future<String?> ask(String text) async {
    calls++;
    if (throws) throw StateError('link dropped');
    return answer;
  }
}

class BoomSkill extends Skill {
  const BoomSkill();
  @override
  String get name => 'boom';
  @override
  String get description => 'always throws';
  @override
  double score(Utterance u) => u.text.contains('boom') ? 1.0 : 0.0;
  @override
  Never run(Utterance u) => throw StateError('skill exploded');
}

void main() {
  group('tier order', () {
    test('answers on-device without touching the remote tiers', () async {
      final laptop = FakeTier(Tier.laptop, answer: 'from laptop');
      final cloud = FakeTier(Tier.cloud, answer: 'from cloud');
      final router = BrainRouter(
        skills: defaultSkills(),
        laptop: laptop,
        cloud: cloud,
      );

      final a = await router.ask('15% of 2400');

      expect(a.text, '360');
      expect(a.tier, Tier.device);
      expect(a.skillName, 'math');
      expect(laptop.calls, 0, reason: 'laptop must not be consulted');
      expect(cloud.calls, 0, reason: 'cloud must not be consulted');
    });

    test('falls through to the laptop when nothing on-device applies', () async {
      final laptop = FakeTier(Tier.laptop, answer: 'Playing your playlist.');
      final cloud = FakeTier(Tier.cloud, answer: 'from cloud');
      final router = BrainRouter(
        skills: defaultSkills(),
        laptop: laptop,
        cloud: cloud,
      );

      final a = await router.ask('play my discover weekly');

      expect(a.text, 'Playing your playlist.');
      expect(a.tier, Tier.laptop);
      expect(laptop.calls, 1);
      expect(cloud.calls, 0, reason: 'laptop answered, so cloud is skipped');
      expect(a.tried, [Tier.device, Tier.laptop]);
    });

    test('skips an unreachable laptop and lands on cloud', () async {
      final laptop = FakeTier(Tier.laptop, available: false, answer: 'nope');
      final cloud = FakeTier(Tier.cloud, answer: 'Delhi is the capital.');
      final router = BrainRouter(
        skills: defaultSkills(),
        laptop: laptop,
        cloud: cloud,
      );

      final a = await router.ask('what is the capital of india');

      expect(a.tier, Tier.cloud);
      expect(laptop.calls, 0);
      expect(cloud.calls, 1);
      expect(a.tried, [Tier.device, Tier.cloud]);
    });

    test('a throwing tier does not end the chain', () async {
      final laptop = FakeTier(Tier.laptop, throws: true);
      final cloud = FakeTier(Tier.cloud, answer: 'cloud caught it');
      final router = BrainRouter(
        skills: defaultSkills(),
        laptop: laptop,
        cloud: cloud,
      );

      final a = await router.ask('tell me a story');

      expect(a.tier, Tier.cloud);
      expect(a.text, 'cloud caught it');
    });

    test('a tier returning null passes the utterance on', () async {
      final laptop = FakeTier(Tier.laptop, answer: null);
      final cloud = FakeTier(Tier.cloud, answer: 'cloud took it');
      final router = BrainRouter(
        skills: defaultSkills(),
        laptop: laptop,
        cloud: cloud,
      );

      final a = await router.ask('tell me a story');

      expect(laptop.calls, 1);
      expect(a.tier, Tier.cloud);
    });

    test('a crashing on-device skill still reaches the laptop', () async {
      final laptop = FakeTier(Tier.laptop, answer: 'laptop rescued it');
      final router = BrainRouter(
        skills: Skills([const BoomSkill()]),
        laptop: laptop,
      );

      final a = await router.ask('boom please');

      expect(a.tier, Tier.laptop);
      expect(a.text, 'laptop rescued it');
    });
  });

  group('unanswered', () {
    test('with no remote tiers, points at what does work offline', () async {
      final router = BrainRouter(skills: defaultSkills());
      final a = await router.ask('play my discover weekly');

      expect(a.tier, Tier.none);
      expect(a.isAnswered, isFalse);
      expect(a.text, contains('offline'));
    });

    test('an empty utterance asks for a repeat', () async {
      final router = BrainRouter(skills: defaultSkills());
      final a = await router.ask('   ');
      expect(a.tier, Tier.none);
      expect(a.text, 'Say that again?');
    });
  });

  group('reach', () {
    test('device is always reachable; absent tiers are not', () {
      final router = BrainRouter(skills: defaultSkills());
      expect(router.reach[Tier.device], isTrue);
      expect(router.reach[Tier.laptop], isFalse);
      expect(router.reach[Tier.cloud], isFalse);
    });

    test('mirrors handler availability', () {
      final router = BrainRouter(
        skills: defaultSkills(),
        laptop: FakeTier(Tier.laptop, available: true),
        cloud: FakeTier(Tier.cloud, available: false),
      );
      expect(router.reach[Tier.laptop], isTrue);
      expect(router.reach[Tier.cloud], isFalse);
    });
  });
}
