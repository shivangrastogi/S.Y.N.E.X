// The brain inside the voice loop: when it's asked, what happens with its
// answer, and that the rule router stays in charge of everything it knows.
import 'dart:io';

import 'package:aeris_assistant/brain/executor.dart';
import 'package:aeris_assistant/brain/llm/brain.dart';
import 'package:aeris_assistant/core/models.dart';
import 'package:aeris_assistant/core/store.dart';
import 'package:aeris_assistant/voice/session.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'fakes.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
      .setMockMethodCallHandler(SystemChannels.platform, (_) async => null); // haptics
  SharedPreferences.setMockInitialValues({});

  late Store store;
  late FakePhone phone;
  late FakeMouth mouth;
  late FakeBrainRuntime model;
  late Directory tempFolder;

  setUp(() => tempFolder = Directory.systemTemp.createTempSync('aeris_brain_test'));
  // The brain appends its log in the background; on Windows a file still
  // being written can't be deleted, so retry briefly.
  tearDown(() async {
    for (var attempt = 0; attempt < 20; attempt++) {
      try {
        tempFolder.deleteSync(recursive: true);
        return;
      } on FileSystemException {
        await Future<void>.delayed(const Duration(milliseconds: 25));
      }
    }
  });

  /// A session whose brain answers with [brainAnswers] (contract JSON, in order).
  Future<VoiceSession> makeSession(List<String?> userSays, List<String> brainAnswers,
      {BrainMode mode = BrainMode.on}) async {
    store = Store.memory()..settings = const Settings(onboarded: true);
    phone = FakePhone();
    mouth = FakeMouth();
    model = FakeBrainRuntime(brainAnswers);
    final modelFolder = Directory('${tempFolder.path}/models')..createSync();
    File('${modelFolder.path}/test-model.gguf').writeAsStringSync('not a real model');
    final brain = AerisBrain(
      runtime: model,
      toolsJsonOverride: File('assets/brain/tools.json').readAsStringSync(),
      supportDirOverride: tempFolder.path,
      modelDirOverride: modelFolder.path,
    );
    await brain.load();
    await brain.setMode(mode);
    return VoiceSession(store: store, ears: FakeEars(userSays), mouth: mouth, exec: Executor(phone, store), brain: brain);
  }

  Future<void> settle() async {
    for (var i = 0; i < 40; i++) {
      await Future<void>.delayed(Duration.zero);
    }
  }

  test('commands the rules know never reach the brain (instant path)', () async {
    final session = await makeSession([], []);
    await session.submitText('torch on karo');
    await settle();
    expect(phone.calls, ['torch true']);
    expect(model.prompts, isEmpty);
    expect(model.loads, 0); // not even loaded
  });

  test('chat the rules don\'t know is answered by the brain', () async {
    final session = await makeSession([], ['{"type":"reply","text":"Arre, chalo ek joke sunata hoon!"}']);
    await session.submitText('yaar bahut bore ho raha hoon');
    await settle();
    expect(mouth.said.single, 'Arre, chalo ek joke sunata hoon!');
    expect(store.activity.single.tool, 'brain');
    expect(phone.calls, isEmpty);
  });

  test('a brain tool call runs through the normal executor', () async {
    final session = await makeSession([], [
      '{"type":"tool_call","calls":[{"name":"set_timer","args":{"duration":"chai ke liye 5 minute"}}]}'
    ]);
    // "chai ke liye" makes the rules give up — the brain still finds the timer
    await session.submitText('chai ke liye 5 minute rakh do');
    await settle();
    expect(phone.calls, ['timer 300']);
  });

  test('the brain sees the time and the matching memory', () async {
    final session = await makeSession([], ['{"type":"reply","text":"B2 mein hai."}']);
    store.addMemory('Meri car B2 parking mein hai');
    await session.submitText('gaadi kidhar chhodi thi maine');
    await settle();
    expect(model.prompts.single, contains('Now: '));
    expect(model.prompts.single, contains('- Meri car B2 parking mein hai'));
  });

  test('when the brain asks, the answer goes back to the brain', () async {
    final session = await makeSession(
      ['usko bolo main 10 minute mein aa raha hoon'],
      [
        '{"type":"ask","text":"Kisko message bhejun?","pending":"send_message"}',
        '{"type":"reply","text":"Theek hai."}',
      ],
    );
    await session.submitText('ek message bhejna hai yaar');
    await settle();
    expect(mouth.said.first, 'Kisko message bhejun?');
    expect(model.prompts.length, 1);
  });

  test('invalid brain output falls back to the rules\' web-search offer', () async {
    // grounding check: the brain invents a contact the user never said
    final session = await makeSession([], [
      '{"type":"tool_call","calls":[{"name":"call","args":{"contact":"Mohan"}}]}'
    ]);
    await session.submitText('kuch interesting batao na');
    await settle();
    expect(phone.calls, isEmpty); // nothing acted on the hallucinated name
    expect(session.approval, isNotNull); // "Google pe search karun?"
  });

  test('a tool this app can\'t run yet falls back instead of acting', () async {
    // (volume used to be the example — the app runs it since 2026-11-17)
    final session = await makeSession([], ['{"type":"tool_call","calls":[{"name":"brightness","args":{"action":"up"}}]}']);
    await session.submitText('screen thodi bright kar do');
    await settle();
    expect(phone.calls, isEmpty);
    expect(session.approval, isNotNull);
  });

  test('mode Off: rules only', () async {
    final session = await makeSession([], ['{"type":"reply","text":"never"}'], mode: BrainMode.off);
    await session.submitText('yaar bahut bore ho raha hoon');
    await settle();
    expect(model.prompts, isEmpty);
  });

  test('shadow mode: the rules act, the brain decides silently and is logged', () async {
    final session = await makeSession([], ['{"type":"tool_call","calls":[{"name":"flashlight","args":{"state":"on"}}]}'],
        mode: BrainMode.shadow);
    await session.submitText('torch on karo');
    await settle();
    expect(phone.calls, ['torch true']); // acted once, by the rules
    expect(model.prompts.length, 1);
    // the log is appended asynchronously after the decision — wait for it
    final logFile = File('${tempFolder.path}/brain_log.jsonl');
    bool logWritten() => logFile.existsSync() && logFile.readAsStringSync().contains('"mode"');
    for (var waited = 0; waited < 50 && !logWritten(); waited++) {
      await Future<void>.delayed(const Duration(milliseconds: 20));
    }
    final log = logFile.readAsStringSync();
    expect(log, contains('"mode":"shadow"'));
  });
}
