// Incoming calls by voice (lib/calls/call_assistant.dart), with fake ears,
// voice, contacts and Android call controls.
import 'dart:async';

import 'package:aeris_assistant/brain/executor.dart';
import 'package:aeris_assistant/calls/call_assistant.dart';
import 'package:aeris_assistant/calls/call_bridge.dart';
import 'package:aeris_assistant/calls/call_voice_rules.dart';
import 'package:aeris_assistant/core/models.dart';
import 'package:aeris_assistant/core/store.dart';
import 'package:aeris_assistant/voice/io.dart';
import 'package:aeris_assistant/voice/session.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';

import 'fakes.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
      .setMockMethodCallHandler(SystemChannels.platform, (_) async => null); // haptics

  late FakeCallBridge bridge;
  late FakeMouth mouth;
  late FakePhone phone;
  late Store store;

  /// [userSays]: what the user answers at each listening turn (null = silence).
  CallAssistant makeAssistant(List<String?> userSays, {bool enabled = true}) {
    store = Store.memory()..settings = Settings(onboarded: true, callsByVoice: enabled);
    bridge = FakeCallBridge();
    mouth = FakeMouth();
    phone = FakePhone();
    final ears = FakeEars(userSays);
    final session = VoiceSession(store: store, ears: ears, mouth: mouth, exec: Executor(phone, store));
    return CallAssistant(
      store: store,
      ears: ears,
      mouth: mouth,
      phone: phone,
      bridge: bridge,
      session: session,
      outcomeHold: Duration.zero,
      ringBeforeSpeaking: Duration.zero,
      ringerFadeDown: Duration.zero,
      ringerFadeUp: Duration.zero,
    )..attach();
  }

  Future<void> settle() async {
    for (var i = 0; i < 40; i++) {
      await Future<void>.delayed(Duration.zero);
    }
  }

  test('a saved contact rings → AERIS names them and answers on "uthao"', () async {
    final assistant = makeAssistant(['haan uthao']);
    await assistant.handleIncomingCall('+91 98765 43210', callerName: 'Ravi Sharma');
    expect(mouth.said.first, 'Ravi Sharma ka call. Uthaun ya kaatun?');
    expect(mouth.lastOutput, SpeechOutput.ringingAloud); // audible while the phone rings
    expect(bridge.actions, ['silence ringer', 'restore ringer', 'answer']);
    expect(bridge.glows, [GlowState.speaking, GlowState.listening, GlowState.accepted, GlowState.off]);
    expect(assistant.phase, CallFlowPhase.idle);
  });

  test('the sentence is made before the ringtone fades, and spoken only after it', () async {
    final assistant = makeAssistant(['uthao']);
    await assistant.handleIncomingCall('9876543210', callerName: 'Ravi Sharma');
    expect(mouth.prepared, ['Ravi Sharma ka call. Uthaun ya kaatun?', 'Uthaun ya kaatun?']);
    expect(bridge.actions.first, 'silence ringer'); // nothing is spoken over the ringtone
    expect(mouth.said.first, 'Ravi Sharma ka call. Uthaun ya kaatun?');
  });

  test('nobody answers by voice → the ringtone fades back in', () async {
    final assistant = CallAssistant(
      store: Store.memory()..settings = const Settings(onboarded: true, callsByVoice: true),
      ears: FakeEars([null, null]),
      mouth: mouth = FakeMouth(),
      phone: FakePhone(),
      bridge: bridge = FakeCallBridge(),
      session: VoiceSession(store: Store.memory(), ears: FakeEars([]), mouth: FakeMouth(), exec: Executor(FakePhone(), Store.memory())),
      outcomeHold: Duration.zero,
      ringBeforeSpeaking: Duration.zero,
      ringerFadeDown: Duration.zero,
      ringerFadeUp: const Duration(milliseconds: 1),
    );
    await assistant.handleIncomingCall('9876543210', callerName: 'Ravi Sharma');
    expect(bridge.actions, ['silence ringer', 'fade ringer back']);
  });

  group('obeys the phone', () {
    test('silent / vibrate without earbuds → completely quiet, no glow', () async {
      final assistant = makeAssistant(['uthao']);
      bridge.situation = const AudioSituation(ringerMode: RingerMode.vibrate);
      await assistant.handleIncomingCall('9876543210', callerName: 'Ravi Sharma');
      expect(mouth.said, isEmpty);
      expect(bridge.glows, isEmpty);
      expect(bridge.actions, isEmpty);
    });

    test('silent / vibrate WITH earbuds → still quiet (the earbuds get no ringtone either)', () async {
      final assistant = makeAssistant(['uthao']);
      bridge.situation = const AudioSituation(ringerMode: RingerMode.vibrate, earbudsConnected: true);
      await assistant.handleIncomingCall('9876543210', callerName: 'Ravi Sharma');
      expect(mouth.said, isEmpty);
      expect(bridge.actions, isEmpty);
    });

    test('ring mode with earbuds → speaks into the earbuds only', () async {
      final assistant = makeAssistant(['uthao']);
      bridge.situation = const AudioSituation(earbudsConnected: true);
      await assistant.handleIncomingCall('9876543210', callerName: 'Ravi Sharma');
      expect(mouth.lastOutput, SpeechOutput.ringingEarbudsOnly);
      expect(bridge.actions, contains('answer'));
    });

    test('earbuds refused by Android → stays quiet instead of using the speaker', () async {
      final assistant = makeAssistant(['uthao']);
      bridge.situation = const AudioSituation(earbudsConnected: true);
      mouth.canBeHeard = false;
      await assistant.handleIncomingCall('9876543210', callerName: 'Ravi Sharma');
      expect(mouth.said.length, 1); // tried once, nobody heard it
      expect(bridge.actions, ['silence ringer', 'restore ringer']); // no listening, no answering
      expect(assistant.phase, CallFlowPhase.idle);
    });

    test('Do Not Disturb → quiet even with earbuds', () {
      expect(voiceForRingingCall(const AudioSituation(doNotDisturb: true, earbudsConnected: true)), isNull);
    });

    test('the rule table', () {
      expect(voiceForRingingCall(const AudioSituation()), SpeechOutput.ringingAloud);
      expect(voiceForRingingCall(const AudioSituation(earbudsConnected: true)), SpeechOutput.ringingEarbudsOnly);
      expect(voiceForRingingCall(const AudioSituation(ringerMode: RingerMode.silent)), isNull);
      expect(voiceForRingingCall(const AudioSituation(ringerMode: RingerMode.silent, earbudsConnected: true)), isNull);
      expect(AudioSituation.fromMap(const {'ringerMode': 'vibrate', 'earbuds': true, 'earbudsName': 'Buds'}).describe(),
          'vibrate, earbuds (Buds)');
    });
  });

  test('"speaker pe uthao" answers on the loudspeaker', () async {
    final assistant = makeAssistant(['speaker pe uthao']);
    await assistant.handleIncomingCall('9876543210', callerName: 'Ravi Sharma');
    expect(bridge.actions, contains('answer on speaker'));
  });

  test('decline a contact → offers the "call you later" text, sends it on "haan"', () async {
    final assistant = makeAssistant(['kaat do', 'haan bhej do']);
    await assistant.handleIncomingCall('9876543210', callerName: 'Ravi Sharma');
    expect(bridge.actions, [
      'silence ringer',
      'restore ringer',
      'reject',
      'sms 9876543210: Abhi busy hoon, thodi der mein baat karte hain.',
    ]);
    expect(mouth.said, [
      'Ravi Sharma ka call. Uthaun ya kaatun?',
      'Ravi ko message bhejun ki baad mein baat karte hain?',
      'Bhej diya.',
    ]);
  });

  test('"nahi" to the text offer sends nothing', () async {
    final assistant = makeAssistant(['kaat do', 'nahi rehne do']);
    await assistant.handleIncomingCall('9876543210', callerName: 'Ravi Sharma');
    expect(bridge.actions.where((a) => a.startsWith('sms')), isEmpty);
  });

  test('an unknown number is declined without a text offer', () async {
    final assistant = makeAssistant(['kaat do']);
    await assistant.handleIncomingCall('9123456780');
    expect(mouth.said.single, 'Ek anjaan number se call aa raha hai. Uthaun ya kaatun?');
    expect(bridge.actions.last, 'reject');
  });

  test('unclear → asks once more; still unclear → lets it ring', () async {
    final assistant = makeAssistant(['kaun hai', null]);
    await assistant.handleIncomingCall('9876543210', callerName: 'Ravi Sharma');
    expect(mouth.said, ['Ravi Sharma ka call. Uthaun ya kaatun?', 'Uthaun ya kaatun?']);
    expect(bridge.actions, ['silence ringer', 'restore ringer']); // no answer, no reject
    expect(bridge.glows.last, GlowState.off);
  });

  test('picked up by touch → AERIS steps back at once', () async {
    final assistant = makeAssistant([]); // the user never speaks
    unawaited(assistant.handleIncomingCall('9876543210', callerName: 'Ravi Sharma'));
    await settle();
    expect(assistant.phase, CallFlowPhase.listening);
    bridge.eventController.add(const CallAnswered());
    await settle();
    expect(assistant.phase, CallFlowPhase.idle);
    expect(bridge.actions, isNot(contains('answer'))); // the phone did it, not AERIS
    expect(bridge.actions.last, 'restore ringer');
    expect(bridge.glows.last, GlowState.off);
  });

  test('ringing events start the flow only when the setting is on', () async {
    makeAssistant(['uthao'], enabled: false);
    bridge.eventController.add(const CallRinging('9876543210', callerName: 'Ravi Sharma'));
    await settle();
    expect(mouth.said, isEmpty);

    makeAssistant(['uthao']);
    bridge.eventController.add(const CallRinging('9876543210', callerName: 'Ravi Sharma'));
    await settle();
    expect(bridge.actions, contains('answer'));
  });

  test('English mode speaks English', () async {
    final assistant = makeAssistant(['pick up']);
    store.settings = store.settings.copyWith(lang: Lang.englishIn);
    await assistant.handleIncomingCall('9876543210', callerName: 'Ravi Sharma');
    expect(mouth.said.first, 'Call from Ravi Sharma. Answer or decline?');
  });

  test('a failure mid-call never leaves AERIS stuck — the next call still works', () async {
    final assistant = makeAssistant(['uthao']); // the failed call never reaches listening
    bridge.failNextGlow = true; // e.g. the overlay window can't be created
    await assistant.handleIncomingCall('9876543210', callerName: 'Ravi Sharma');
    expect(assistant.phase, CallFlowPhase.idle);
    expect(bridge.actions.last, 'restore ringer');

    await assistant.handleIncomingCall('9876543210', callerName: 'Ravi Sharma');
    expect(bridge.actions.last, 'answer');
  });

  test('the setting is saved and restored', () {
    const settings = Settings(callsByVoice: true);
    expect(Settings.fromJson(settings.toJson()).callsByVoice, isTrue);
    expect(Settings.fromJson(const {}).callsByVoice, isFalse); // older saved settings
  });
}
