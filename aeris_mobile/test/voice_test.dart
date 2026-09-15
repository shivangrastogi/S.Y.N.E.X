import 'package:aeris_mobile/brain/router.dart';
import 'package:aeris_mobile/design/theme.dart';
import 'package:aeris_mobile/skills/builtin/builtins.dart';
import 'package:aeris_mobile/state/conversation.dart';
import 'package:aeris_mobile/ui/chat_screen.dart';
import 'package:aeris_mobile/voice/voice.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

/// A microphone under test control: [emit] plays a transcript through whatever
/// callback the UI registered.
class FakeVoiceIn implements VoiceIn {
  FakeVoiceIn({this.available = true});

  final bool available;
  TranscriptCallback? _onText;
  bool _listening = false;
  int startCount = 0;
  int stopCount = 0;

  @override
  bool get isAvailable => available;

  @override
  bool get isListening => _listening;

  @override
  Future<bool> init() async => available;

  @override
  Future<void> start(TranscriptCallback onText) async {
    startCount++;
    _listening = true;
    _onText = onText;
  }

  @override
  Future<void> stop() async {
    stopCount++;
    _listening = false;
  }

  @override
  void dispose() {}

  void emit(String text, {bool isFinal = false}) {
    if (isFinal) _listening = false;
    _onText?.call(text, isFinal);
  }
}

class FakeVoiceOut implements VoiceOut {
  FakeVoiceOut({this.available = true});

  final bool available;
  final List<String> spoken = [];
  int stopCount = 0;

  @override
  bool get isAvailable => available;

  @override
  Future<bool> init() async => available;

  @override
  Future<void> speak(String text) async => spoken.add(text);

  @override
  Future<void> stop() async => stopCount++;

  @override
  void dispose() {}
}

Widget harness({
  required VoiceIn voiceIn,
  required VoiceOut voiceOut,
}) {
  final skills = defaultSkills();
  return MaterialApp(
    theme: AerisTheme.dark(),
    home: ChatScreen(
      conversation: Conversation(BrainRouter(skills: skills)),
      skills: skills,
      voiceIn: voiceIn,
      voiceOut: voiceOut,
    ),
  );
}

void main() {
  group('speakable', () {
    test('keeps Latin and Devanagari, drops what cannot be pronounced', () {
      expect(speakable('Namaste 🙏 दोस्त'), 'Namaste दोस्त');
      expect(speakable('86°F'), '86 F');
      expect(speakable('  spaced   out  '), 'spaced out');
    });

    test('collapses to empty when nothing sayable remains', () {
      expect(speakable('🎉🎉'), '');
    });
  });

  group('silent implementations', () {
    test('report unavailable and do nothing', () async {
      final vin = SilentVoiceIn();
      final vout = SilentVoiceOut();
      expect(await vin.init(), isFalse);
      expect(await vout.init(), isFalse);
      expect(vin.isAvailable, isFalse);
      expect(vout.isAvailable, isFalse);
      // Must not throw.
      await vin.start((_, _) {});
      await vin.stop();
      await vout.speak('hello');
      await vout.stop();
    });
  });

  group('microphone in the composer', () {
    testWidgets('is hidden when speech is unavailable', (tester) async {
      await tester.pumpWidget(harness(
        voiceIn: FakeVoiceIn(available: false),
        voiceOut: FakeVoiceOut(),
      ));
      expect(find.byIcon(Icons.mic_none), findsNothing);
    });

    testWidgets('is offered when speech is available', (tester) async {
      await tester.pumpWidget(harness(
        voiceIn: FakeVoiceIn(),
        voiceOut: FakeVoiceOut(),
      ));
      expect(find.byIcon(Icons.mic_none), findsOneWidget);
    });

    testWidgets('tapping it starts listening and shows the indicator',
        (tester) async {
      final vin = FakeVoiceIn();
      await tester.pumpWidget(harness(voiceIn: vin, voiceOut: FakeVoiceOut()));

      await tester.tap(find.byIcon(Icons.mic_none));
      await tester.pump();

      expect(vin.startCount, 1);
      expect(find.text('LISTENING'), findsOneWidget);
      expect(find.byIcon(Icons.stop), findsOneWidget);
    });

    testWidgets('tapping again stops listening', (tester) async {
      final vin = FakeVoiceIn();
      await tester.pumpWidget(harness(voiceIn: vin, voiceOut: FakeVoiceOut()));

      await tester.tap(find.byIcon(Icons.mic_none));
      await tester.pump();
      await tester.tap(find.byIcon(Icons.stop));
      await tester.pump();

      expect(vin.stopCount, 1);
      expect(find.text('LISTENING'), findsNothing);
    });

    testWidgets('partial results fill the field without sending',
        (tester) async {
      final vin = FakeVoiceIn();
      await tester.pumpWidget(harness(voiceIn: vin, voiceOut: FakeVoiceOut()));

      await tester.tap(find.byIcon(Icons.mic_none));
      await tester.pump();
      vin.emit('fifteen percent');
      await tester.pump();

      expect(find.widgetWithText(TextField, 'fifteen percent'), findsOneWidget);
      expect(find.text('360'), findsNothing, reason: 'not final yet');
    });
  });

  group('speaking', () {
    testWidgets('a final transcript is answered and spoken', (tester) async {
      final vin = FakeVoiceIn();
      final vout = FakeVoiceOut();
      await tester.pumpWidget(harness(voiceIn: vin, voiceOut: vout));

      await tester.tap(find.byIcon(Icons.mic_none));
      await tester.pump();
      vin.emit('15% of 2400', isFinal: true);
      await tester.pumpAndSettle();

      expect(find.text('360'), findsOneWidget);
      expect(vout.spoken, ['360']);
      expect(find.text('LISTENING'), findsNothing);
    });

    testWidgets('a typed turn is answered but NOT spoken', (tester) async {
      final vout = FakeVoiceOut();
      await tester.pumpWidget(harness(voiceIn: FakeVoiceIn(), voiceOut: vout));

      await tester.enterText(find.byType(TextField), '15% of 2400');
      await tester.testTextInput.receiveAction(TextInputAction.send);
      await tester.pumpAndSettle();

      expect(find.text('360'), findsOneWidget);
      expect(vout.spoken, isEmpty,
          reason: 'typing in a quiet room must not make the phone talk');
    });

    testWidgets('starting the mic cuts off speech already in progress',
        (tester) async {
      final vin = FakeVoiceIn();
      final vout = FakeVoiceOut();
      await tester.pumpWidget(harness(voiceIn: vin, voiceOut: vout));

      await tester.tap(find.byIcon(Icons.mic_none));
      await tester.pump();

      expect(vout.stopCount, greaterThan(0),
          reason: 'the recogniser would otherwise transcribe A.E.R.I.S itself');
    });

    testWidgets('an unanswered voice turn still speaks the fallback',
        (tester) async {
      final vin = FakeVoiceIn();
      final vout = FakeVoiceOut();
      await tester.pumpWidget(harness(voiceIn: vin, voiceOut: vout));

      await tester.tap(find.byIcon(Icons.mic_none));
      await tester.pump();
      vin.emit('play my discover weekly', isFinal: true);
      await tester.pumpAndSettle();

      expect(vout.spoken, hasLength(1));
      expect(vout.spoken.first, contains('offline'));
    });
  });
}
