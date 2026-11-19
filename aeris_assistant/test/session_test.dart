import 'package:aeris_assistant/brain/executor.dart';
import 'package:aeris_assistant/core/models.dart';
import 'package:aeris_assistant/core/store.dart';
import 'package:aeris_assistant/voice/session.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';

import 'fakes.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  // HapticFeedback goes through a platform channel — silence it.
  TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
      .setMockMethodCallHandler(SystemChannels.platform, (_) async => null);

  late Store store;
  late FakePhone phone;
  late FakeMouth mouth;

  VoiceSession make(List<String?> script) {
    store = Store.memory()..settings = const Settings(onboarded: true);
    store.protocols.addAll(Store.defaultProtocols());
    phone = FakePhone();
    mouth = FakeMouth();
    return VoiceSession(store: store, ears: FakeEars(script), mouth: mouth, exec: Executor(phone, store));
  }

  Future<void> settle() async {
    for (var i = 0; i < 20; i++) {
      await Future<void>.delayed(Duration.zero);
    }
  }

  test('voice command runs, speaks, logs, keeps listening', () async {
    final s = make(['kal subah 6:30 ka alarm laga do']);
    await s.start();
    await settle();
    expect(phone.calls, ['alarm 6:30']);
    expect(mouth.said.single, '6:30 a.m. ka alarm laga diya.');
    expect(store.activity.single.tool, 'alarm');
    expect(store.activity.single.status, TurnStatus.ok);
    expect(s.phase, Phase.listening); // keep-listening is on by default
  });

  test('typed command does not re-listen', () async {
    final s = make([]);
    await s.submitText('battery kitni hai');
    await settle();
    expect(mouth.said.single, 'Battery 82% hai.');
    expect(s.phase, Phase.idle);
    expect(store.activity.single.typed, isTrue);
  });

  test('message waits for "haan" before anything leaves', () async {
    final s = make(['Ravi ko WhatsApp karo ki main late hoon', 'haan bhejo']);
    await s.start();
    await settle();
    expect(phone.calls.single, 'wa 98765 43210 main late hoon');
    expect(mouth.said.first, contains('Ravi Sharma ko ye bhejun'));
    expect(store.activity.single.said, 'Ravi ko WhatsApp karo ki main late hoon');
  });

  test('"mat bhejo" cancels — nothing sent', () async {
    final s = make(['Ravi ko WhatsApp karo ki main late hoon', 'mat bhejo']);
    await s.start();
    await settle();
    expect(phone.calls, isEmpty);
    expect(store.activity.single.status, TurnStatus.cancelled);
  });

  test('tap approve works for typed commands', () async {
    final s = make([]);
    await s.submitText('Mummy ko whatsapp karo ki khana ready hai');
    await settle();
    expect(s.phase, Phase.approval);
    expect(s.approval!.to, 'Mummy');
    s.approve();
    await settle();
    expect(phone.calls.single, startsWith('wa 99999 00000'));
  });

  test('unknown contact fails before approval', () async {
    final s = make([]);
    await s.submitText('Zoya ko whatsapp karo ki hi');
    await settle();
    expect(s.approval, isNull);
    expect(store.activity.single.status, TurnStatus.failed);
    expect(phone.calls, isEmpty);
  });

  test('clarify: "alarm laga do" → asks time → answer completes it', () async {
    final s = make(['alarm laga do', 'subah 7 baje']);
    await s.start();
    await settle();
    expect(mouth.said.first, 'Kis time ka alarm lagaun?');
    expect(phone.calls, ['alarm 7:0']);
  });

  test('"bas" ends the conversation', () async {
    final s = make(['bas']);
    await s.start();
    await settle();
    expect(s.active, isFalse);
    expect(mouth.said.single, 'Theek hai, bye!');
  });

  test('protocol runs its actions and says its line', () async {
    final s = make([]);
    await s.submitText('focus mode');
    await settle();
    expect(phone.calls, ['timer 1500', 'ringer vibrate']); // it really goes quiet now
    expect(mouth.said.single, 'Focus timer started, phone on vibrate.');
  });

  test('cancelling a web search does not say "nahi bheja" (phone bug, 2026-11-17)', () async {
    final s = make([]);
    await s.submitText('quantum physics samjhao');
    await settle();
    expect(s.phase, Phase.approval);
    s.deny();
    await settle();
    expect(mouth.said.last, 'Theek hai, rehne dete hain.');
    expect(phone.calls, isEmpty);
  });

  test('two silences close the overlay', () async {
    final s = make([null, null]);
    await s.start();
    await settle();
    expect(s.phase, Phase.noSignal);
    await s.retry();
    await settle();
    expect(s.active, isFalse);
  });

  test('English mode replies in English', () async {
    final s = make([]);
    store.settings = const Settings(onboarded: true, lang: Lang.englishIn);
    await s.submitText('torch on');
    await settle();
    expect(mouth.said.single, 'Torch on.');
    await s.submitText('12 into 8');
    await settle();
    expect(mouth.said.last, '96');
  });

  test('remember then recall', () async {
    final s = make([]);
    await s.submitText('yaad rakho ki meri car B2 mein parked hai');
    await settle();
    expect(store.memories.single.text, 'Meri car B2 mein parked hai');
    await s.submitText('car kahan park ki thi');
    await settle();
    expect(mouth.said.last, contains('B2'));
  });
}
