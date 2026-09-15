import 'package:aeris_mobile/brain/router.dart';
import 'package:aeris_mobile/brain/tier.dart';
import 'package:aeris_mobile/skills/builtin/builtins.dart';
import 'package:aeris_mobile/state/conversation.dart';
import 'package:aeris_mobile/store/transcript_store.dart';
import 'package:flutter_test/flutter_test.dart';

Conversation build(TranscriptStore store) =>
    Conversation(BrainRouter(skills: defaultSkills()), store: store);

void main() {
  group('Message serialisation', () {
    test('round-trips every field', () {
      final original = Message(
        text: '360',
        fromUser: false,
        at: DateTime.fromMillisecondsSinceEpoch(1785749328000),
        tier: Tier.device,
        detail: '15% of 2,400 =',
        skillName: 'math',
        elapsed: const Duration(microseconds: 1234),
      );

      final back = Message.fromJson(original.toJson())!;

      expect(back.text, '360');
      expect(back.fromUser, isFalse);
      expect(back.at, original.at);
      expect(back.tier, Tier.device);
      expect(back.detail, '15% of 2,400 =');
      expect(back.skillName, 'math');
      expect(back.elapsed, const Duration(microseconds: 1234));
    });

    test('round-trips a user turn with no answer fields', () {
      final back = Message.fromJson(Message.user('hello').toJson())!;
      expect(back.text, 'hello');
      expect(back.fromUser, isTrue);
      expect(back.tier, isNull);
      expect(back.elapsed, isNull);
    });

    test('returns null for malformed entries rather than throwing', () {
      expect(Message.fromJson(null), isNull);
      expect(Message.fromJson('not a map'), isNull);
      expect(Message.fromJson({}), isNull);
      expect(Message.fromJson({'text': 'hi'}), isNull);
      expect(Message.fromJson({'text': 1, 'fromUser': true, 'at': 0}), isNull);
    });

    test('drops a tier name it does not recognise instead of failing', () {
      final back = Message.fromJson({
        'text': 'x',
        'fromUser': false,
        'at': 0,
        'tier': 'quantum',
      });
      expect(back, isNotNull);
      expect(back!.tier, isNull);
    });
  });

  group('Conversation persistence', () {
    test('saves after a turn and restores into a new instance', () async {
      final store = MemoryTranscriptStore();

      final first = build(store);
      await first.send('15% of 2400');
      expect(first.messages, hasLength(2));

      final second = build(store);
      expect(second.isEmpty, isTrue, reason: 'nothing restored yet');
      await second.restore();

      expect(second.messages, hasLength(2));
      expect(second.messages[0].text, '15% of 2400');
      expect(second.messages[1].text, '360');
      expect(second.messages[1].tier, Tier.device);
      expect(second.messages[1].skillName, 'math');
    });

    test('never persists the pending placeholder', () async {
      final store = MemoryTranscriptStore();
      final convo = build(store);
      await convo.send('2 + 2');

      final saved = await store.load();
      expect(saved.any((m) => m.pending), isFalse);
      expect(saved, hasLength(2));
    });

    test('clearing wipes the stored transcript too', () async {
      final store = MemoryTranscriptStore();
      final convo = build(store);
      await convo.send('2 + 2');
      convo.clear();

      // clear() persists in the background, so let the microtask run.
      await Future<void>.delayed(Duration.zero);
      expect(await store.load(), isEmpty);

      final fresh = build(store);
      await fresh.restore();
      expect(fresh.isEmpty, isTrue);
    });

    test('restoring an empty store leaves the transcript alone', () async {
      final convo = build(MemoryTranscriptStore());
      await convo.restore();
      expect(convo.isEmpty, isTrue);
    });

    test('trims history to the cap', () async {
      final store = MemoryTranscriptStore();
      final convo = build(store);

      // Each turn adds two messages, so this crosses the cap.
      for (var i = 0; i < Conversation.keep ~/ 2 + 5; i++) {
        await convo.send('$i + 1');
      }

      expect(convo.messages.length, lessThanOrEqualTo(Conversation.keep));
      // The newest turn survived; the oldest did not.
      expect(convo.messages.last.text, isNotEmpty);
      expect(convo.messages.first.text, isNot('0 + 1'));
    });

    test('defaults to in-memory when no store is given', () async {
      final convo = Conversation(BrainRouter(skills: defaultSkills()));
      await convo.send('2 + 2');
      expect(convo.messages, hasLength(2));
      await convo.restore(); // must not throw
    });
  });
}
