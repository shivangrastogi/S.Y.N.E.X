// One voice, one speed: the Settings slider drives every place AERIS speaks.
import 'package:aeris_assistant/brain/executor.dart';
import 'package:aeris_assistant/calls/call_assistant.dart';
import 'package:aeris_assistant/core/models.dart';
import 'package:aeris_assistant/core/store.dart';
import 'package:aeris_assistant/voice/local/local_mouth.dart';
import 'package:aeris_assistant/voice/session.dart';
import 'package:aeris_assistant/voice/voice_speed_sync.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';

import 'fakes.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
      .setMockMethodCallHandler(SystemChannels.platform, (_) async => null); // haptics

  test('the speed formula: 0.5 on the slider = 1.0x = the picked sample', () {
    expect(LocalMouth.speedFor(0.5), 1.0);
    expect(LocalMouth.speedFor(0.6), closeTo(1.2, 1e-9));
    expect(LocalMouth.speedFor(0.4), closeTo(0.8, 1e-9));
  });

  test('a call speaks at exactly the Settings speed (no call-only pace)', () async {
    final store = Store.memory()..settings = const Settings(onboarded: true, callsByVoice: true, rate: 0.6);
    final mouth = FakeMouth();
    final calls = CallAssistant(
      store: store,
      ears: FakeEars(['uthao']),
      mouth: mouth,
      phone: FakePhone(),
      bridge: FakeCallBridge(),
      session: VoiceSession(store: store, ears: FakeEars([]), mouth: FakeMouth(), exec: Executor(FakePhone(), store)),
      outcomeHold: Duration.zero,
      ringBeforeSpeaking: Duration.zero,
      ringerFadeDown: Duration.zero,
      ringerFadeUp: Duration.zero,
    );
    await calls.handleIncomingCall('9876543210', callerName: 'Ravi Sharma');
    expect(mouth.lastRate, 0.6);
  });

  test('changing the speed re-makes the pre-made phrases at the new speed', () async {
    final store = Store.memory()..settings = const Settings(onboarded: true);
    final mouth = FakeMouth();
    final sync = VoiceSpeedSync(store: store, mouth: mouth, settleDelay: const Duration(milliseconds: 10));
    await sync.start();
    expect(mouth.lastRate, 0.5);
    final firstRound = mouth.prepared.length;
    expect(firstRound, greaterThan(0));

    store.updateSettings(store.settings.copyWith(rate: 0.7));
    await Future<void>.delayed(const Duration(milliseconds: 50));
    expect(mouth.lastRate, 0.7);
    expect(mouth.prepared.length, 2 * firstRound); // the same phrases again, new speed

    store.updateSettings(store.settings.copyWith(name: 'Shivang')); // not a speed change
    await Future<void>.delayed(const Duration(milliseconds: 50));
    expect(mouth.prepared.length, 2 * firstRound);
    sync.dispose();
  });
}
