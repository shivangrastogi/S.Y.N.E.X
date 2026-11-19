// Pre-made announcements for likely callers (lib/calls/caller_voice_prep.dart).
import 'package:aeris_assistant/calls/caller_voice_prep.dart';
import 'package:aeris_assistant/core/models.dart';
import 'package:aeris_assistant/core/store.dart';
import 'package:flutter_test/flutter_test.dart';

import 'fakes.dart';

void main() {
  late Store store;
  late FakeMouth mouth;
  late FakeCallBridge bridge;

  CallerVoicePrep makePrep({bool charging = false, bool Function()? isBusy}) {
    store = Store.memory()..settings = const Settings(onboarded: true, callsByVoice: true, rate: 0.6);
    mouth = FakeMouth();
    bridge = FakeCallBridge()..callers = [for (var i = 1; i <= 50; i++) 'Caller $i'];
    return CallerVoicePrep(
      store: store,
      mouth: mouth,
      bridge: bridge,
      isCharging: () async => charging,
      isBusy: isBusy ?? () => false,
      busyRecheck: const Duration(milliseconds: 5),
    );
  }

  test('makes the exact announcement a real call will ask for, at the Settings speed', () async {
    final prep = makePrep();
    await prep.run();
    expect(mouth.prepared.first, 'Caller 1 ka call. Uthaun ya kaatun?');
    expect(mouth.lastRate, 0.6);
  });

  test('top 10 on battery, up to 40 while charging', () async {
    await makePrep().run();
    expect(mouth.prepared.length, 10);
    await makePrep(charging: true).run();
    expect(mouth.prepared.length, 40);
  });

  test('waits while AERIS is busy talking or handling a call', () async {
    var busy = true;
    final prep = makePrep(isBusy: () => busy);
    final running = prep.run();
    await Future<void>.delayed(const Duration(milliseconds: 30));
    expect(mouth.prepared, isEmpty);
    busy = false;
    await running;
    expect(mouth.prepared.length, 10);
  });

  test('does nothing when calls by voice is off', () async {
    final prep = makePrep();
    store.settings = store.settings.copyWith(callsByVoice: false);
    expect(await prep.run(), 0);
    expect(mouth.prepared, isEmpty);
  });

  test('English app → English announcements', () async {
    final prep = makePrep();
    store.settings = store.settings.copyWith(lang: Lang.englishIn);
    await prep.run();
    expect(mouth.prepared.first, 'Call from Caller 1. Answer or decline?');
  });
}
