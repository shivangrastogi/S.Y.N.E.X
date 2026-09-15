import 'package:aeris_mobile/brain/router.dart';
import 'package:aeris_mobile/design/theme.dart';
import 'package:aeris_mobile/skills/builtin/builtins.dart';
import 'package:aeris_mobile/skills/builtin/help_skill.dart';
import 'package:aeris_mobile/skills/skill.dart';
import 'package:aeris_mobile/skills/utterance.dart';
import 'package:aeris_mobile/state/conversation.dart';
import 'package:aeris_mobile/ui/chat_screen.dart';
import 'package:aeris_mobile/voice/voice.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  final skills = defaultSkills();

  SkillReply help(String text) =>
      skills.select(Utterance(text))!.run(Utterance(text)) as SkillReply;

  group('HelpSkill', () {
    test('claims the ways people ask, including Hinglish', () {
      for (final text in const [
        'what can you do',
        'what can i say',
        'kya kar sakte ho',
        'help',
        'madad',
        'show commands',
      ]) {
        expect(skills.select(Utterance(text))?.name, 'help', reason: text);
      }
    });

    test('does not hijack "help" inside a real request', () {
      expect(skills.select(Utterance('help me split 2400 between 4'))?.name,
          'finance');
    });

    test('lists every other skill, and never itself', () {
      final reply = help('what can you do');
      for (final s in skills.all) {
        if (s.name == 'help') continue;
        expect(reply.text, contains(s.name.toUpperCase()), reason: s.name);
      }
      expect(reply.text, isNot(contains('HELP')));
    });

    test('shows examples, capped per skill', () {
      final reply = help('what can you do');
      // The maths skill has more examples than the cap, so the third must
      // not appear.
      expect(reply.text, contains('23 * 4 + 7'));
      expect(reply.text, contains('15% of 2400'));
      expect(reply.text, isNot(contains('2400 ka 15 percent')));
    });

    test('counts from the live registry rather than a constant', () {
      final reply = help('what can you do');
      final others = skills.all.where((s) => s.name != 'help').length;
      expect(reply.detail, contains('$others skills'));
    });

    test('says so when the registry is empty', () {
      final lonely = HelpSkill(() => const []);
      expect(lonely.run(Utterance('help')).text, 'No skills are loaded.');
    });
  });

  group('copy an answer', () {
    testWidgets('long-pressing a reply copies its text', (tester) async {
      final copied = <String>[];
      tester.binding.defaultBinaryMessenger.setMockMethodCallHandler(
        SystemChannels.platform,
        (call) async {
          if (call.method == 'Clipboard.setData') {
            copied.add((call.arguments as Map)['text'] as String);
          }
          return null;
        },
      );
      addTearDown(() => tester.binding.defaultBinaryMessenger
          .setMockMethodCallHandler(SystemChannels.platform, null));

      final s = defaultSkills();
      final convo = Conversation(BrainRouter(skills: s));
      await tester.pumpWidget(MaterialApp(
        theme: AerisTheme.dark(),
        home: ChatScreen(
          conversation: convo,
          skills: s,
          voiceIn: SilentVoiceIn(),
          voiceOut: SilentVoiceOut(),
        ),
      ));

      await tester.enterText(find.byType(TextField), '15% of 2400');
      await tester.testTextInput.receiveAction(TextInputAction.send);
      await tester.pumpAndSettle();

      await tester.longPress(find.text('360'));
      await tester.pumpAndSettle();

      expect(copied, ['360']);
      expect(find.text('Copied'), findsOneWidget);
    });
  });
}
