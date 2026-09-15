import 'package:aeris_mobile/brain/router.dart';
import 'package:aeris_mobile/brain/tier.dart';
import 'package:aeris_mobile/design/theme.dart';
import 'package:aeris_mobile/skills/builtin/builtins.dart';
import 'package:aeris_mobile/state/conversation.dart';
import 'package:aeris_mobile/ui/chat_screen.dart';
import 'package:aeris_mobile/ui/widgets/message_bubble.dart';
import 'package:aeris_mobile/voice/voice.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

Widget bubble(Message m, {bool disableAnimations = false}) => MaterialApp(
      theme: AerisTheme.dark(),
      home: MediaQuery(
        data: MediaQueryData(disableAnimations: disableAnimations),
        child: Scaffold(body: MessageBubble(message: m)),
      ),
    );

Widget chat({bool disableAnimations = false}) {
  final skills = defaultSkills();
  return MaterialApp(
    theme: AerisTheme.dark(),
    home: MediaQuery(
      data: MediaQueryData(disableAnimations: disableAnimations),
      child: ChatScreen(
        conversation: Conversation(BrainRouter(skills: skills)),
        skills: skills,
        voiceIn: SilentVoiceIn(),
        voiceOut: SilentVoiceOut(),
      ),
    ),
  );
}

void main() {
  group('screen reader labels', () {
    testWidgets('a user turn is announced as theirs', (tester) async {
      await tester.pumpWidget(bubble(Message.user('15% of 2400')));

      final node = tester.getSemantics(find.byType(MessageBubble));
      expect(node.label, contains('You said'));
      expect(node.value, '15% of 2400');
    });

    testWidgets('an answer carries its provenance, not just its text',
        (tester) async {
      await tester.pumpWidget(bubble(Message.answer(const Answer(
        text: '360',
        tier: Tier.device,
        skillName: 'math',
        elapsed: Duration(milliseconds: 3),
      ))));

      final node = tester.getSemantics(find.byType(MessageBubble));
      expect(node.label, contains('answered on this phone'));
      expect(node.label, contains('by math'));
      expect(node.value, '360');
    });

    testWidgets('each tier is described in words', (tester) async {
      for (final (tier, phrase) in const [
        (Tier.laptop, 'answered by the laptop'),
        (Tier.cloud, 'answered from the cloud'),
        (Tier.none, 'could not be answered'),
      ]) {
        await tester.pumpWidget(bubble(Message.answer(Answer(
          text: 'x',
          tier: tier,
          elapsed: Duration.zero,
        ))));
        final node = tester.getSemantics(find.byType(MessageBubble));
        expect(node.label, contains(phrase), reason: tier.name);
      }
    });

    testWidgets('the thinking placeholder announces itself', (tester) async {
      await tester.pumpWidget(bubble(Message.thinking()));
      final node = tester.getSemantics(find.byType(MessageBubble));
      expect(node.label, contains('thinking'));
    });

    testWidgets('the reach strip describes each tier', (tester) async {
      await tester.pumpWidget(chat());
      expect(
        find.bySemanticsLabel(RegExp('on-device reachable')),
        findsOneWidget,
      );
      expect(
        find.bySemanticsLabel(RegExp('laptop not reachable')),
        findsOneWidget,
      );
    });
  });

  group('reduced motion', () {
    testWidgets('the thinking dots hold still when animations are off',
        (tester) async {
      await tester.pumpWidget(bubble(Message.thinking(),
          disableAnimations: true));

      // pumpAndSettle times out on a repeating animation; completing proves
      // nothing is still running.
      await tester.pumpAndSettle();
      expect(find.byType(MessageBubble), findsOneWidget);
    });

    testWidgets('the thinking dots do animate when motion is allowed',
        (tester) async {
      await tester.pumpWidget(bubble(Message.thinking()));
      await tester.pump(const Duration(milliseconds: 100));

      expect(tester.binding.hasScheduledFrame, isTrue,
          reason: 'a repeating animation keeps requesting frames');
    });

    testWidgets('the listening pulse holds still too', (tester) async {
      await tester.pumpWidget(chat(disableAnimations: true));
      await tester.pumpAndSettle();
      expect(find.byType(ChatScreen), findsOneWidget);
    });

    testWidgets('sending a turn settles with animations off', (tester) async {
      await tester.pumpWidget(chat(disableAnimations: true));

      await tester.enterText(find.byType(TextField), '15% of 2400');
      await tester.testTextInput.receiveAction(TextInputAction.send);
      await tester.pumpAndSettle();

      expect(find.text('360'), findsOneWidget);
    });
  });
}
