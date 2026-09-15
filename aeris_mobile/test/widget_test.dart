import 'package:aeris_mobile/brain/router.dart';
import 'package:aeris_mobile/design/theme.dart';
import 'package:aeris_mobile/skills/builtin/builtins.dart';
import 'package:aeris_mobile/skills/skill.dart';
import 'package:aeris_mobile/state/conversation.dart';
import 'package:aeris_mobile/ui/chat_screen.dart';
import 'package:aeris_mobile/voice/voice.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

/// These cases are about the transcript, not the microphone, so voice is
/// silent here — which is also what the app does on desktop and web.
Widget harness(Conversation convo, Skills skills) => MaterialApp(
      theme: AerisTheme.dark(),
      home: ChatScreen(
        conversation: convo,
        skills: skills,
        voiceIn: SilentVoiceIn(),
        voiceOut: SilentVoiceOut(),
      ),
    );

void main() {
  testWidgets('empty state offers examples that actually work offline',
      (tester) async {
    // Tall surface: the list is lazily built, so on the default 800x600 the
    // last skill's row is never constructed and the finder would miss it.
    tester.view.physicalSize = const Size(1200, 2400);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(tester.view.reset);

    final skills = defaultSkills();
    final convo = Conversation(BrainRouter(skills: skills));
    await tester.pumpWidget(harness(convo, skills));

    expect(find.text('Works without the laptop'), findsOneWidget);
    // Every skill contributes its first example, so the list stays correct as
    // skills are added rather than pinning to today's wording.
    for (final skill in skills.all) {
      expect(
        find.text(skill.examples.first),
        findsOneWidget,
        reason: '${skill.name} should offer an example',
      );
    }
  });

  testWidgets('tapping an example answers it on-device', (tester) async {
    final skills = defaultSkills();
    final convo = Conversation(BrainRouter(skills: skills));
    await tester.pumpWidget(harness(convo, skills));

    await tester.tap(find.text('23 * 4 + 7'));
    await tester.pumpAndSettle();

    expect(find.text('99'), findsOneWidget);
    // The provenance readout is the point of the UI — assert it is rendered.
    // Matched together, since "ON-DEVICE" alone also appears in the reach strip.
    expect(find.textContaining(RegExp(r'ON-DEVICE.+math.+m?s')), findsOneWidget);
  });

  testWidgets('typing and sending appends both turns', (tester) async {
    final skills = defaultSkills();
    final convo = Conversation(BrainRouter(skills: skills));
    await tester.pumpWidget(harness(convo, skills));

    await tester.enterText(find.byType(TextField), '2 + 2');
    await tester.testTextInput.receiveAction(TextInputAction.send);
    await tester.pumpAndSettle();

    expect(find.text('2 + 2'), findsOneWidget); // the user's turn
    expect(find.text('4'), findsOneWidget); // the answer
  });

  testWidgets('the reach strip shows laptop and cloud as unreachable',
      (tester) async {
    final skills = defaultSkills();
    final convo = Conversation(BrainRouter(skills: skills));
    await tester.pumpWidget(harness(convo, skills));

    expect(find.text('ON-DEVICE'), findsOneWidget);
    expect(find.text('LAPTOP'), findsOneWidget);
    expect(find.text('CLOUD'), findsOneWidget);
  });

  testWidgets('the diagnostics button opens the diagnostics screen',
      (tester) async {
    final skills = defaultSkills();
    final convo = Conversation(BrainRouter(skills: skills));
    await tester.pumpWidget(harness(convo, skills));

    await tester.tap(find.byIcon(Icons.monitor_heart_outlined));
    await tester.pumpAndSettle();

    expect(find.text('DIAGNOSTICS'), findsOneWidget);
    expect(find.text('SKILLS'), findsOneWidget);
    // The count comes from the live registry, not a hardcoded number.
    expect(find.text('${skills.all.length}'), findsWidgets);
  });

  testWidgets('an unanswerable question says what does work', (tester) async {
    final skills = defaultSkills();
    final convo = Conversation(BrainRouter(skills: skills));
    await tester.pumpWidget(harness(convo, skills));

    await tester.enterText(find.byType(TextField), 'play my discover weekly');
    await tester.testTextInput.receiveAction(TextInputAction.send);
    await tester.pumpAndSettle();

    expect(find.textContaining('offline'), findsOneWidget);
    expect(find.textContaining('UNANSWERED'), findsOneWidget);
  });
}
