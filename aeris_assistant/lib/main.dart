import 'dart:async';

import 'package:battery_plus/battery_plus.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import 'app/app.dart';
import 'app/scope.dart';
import 'brain/executor.dart';
import 'brain/llm/brain.dart';
import 'brain/phone.dart';
import 'calls/call_assistant.dart';
import 'calls/call_bridge.dart';
import 'calls/caller_voice_prep.dart';
import 'core/store.dart';
import 'features/settings/voice_check.dart';
import 'ui/theme.dart';
import 'voice/io.dart';
import 'voice/local/local_ears.dart';
import 'voice/local/local_mouth.dart';
import 'voice/local/model_store.dart';
import 'voice/local/speech_worker.dart';
import 'voice/switching.dart';
import 'voice/session.dart';
import 'voice/voice_speed_sync.dart';

/// Runs when the app opens — and also with NO screen at all, when the call
/// watcher restarts AERIS in the background (android/.../AerisEngine.kt).
/// So nothing here may depend on a window existing.
Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  _styleSystemBars();

  final store = await Store.open();
  final jarvis = LocalMouth();
  final ears = SwitchEars(store: store, local: LocalEars(), google: DeviceEars());
  final phone = AndroidPhone();
  final brain = AerisBrain(); // on-device LLM; settings + model scan load below
  final session = VoiceSession(
    store: store,
    ears: ears,
    mouth: jarvis, // the only voice (Supertonic male 9, on this phone)
    exec: Executor(phone, store),
    brain: brain,
  );
  // Incoming calls by voice: shares the same ears and voice as the session.
  final callBridge = AndroidCallBridge();
  final calls = CallAssistant(store: store, ears: ears, mouth: jarvis, phone: phone, bridge: callBridge, session: session)
    ..attach();
  // Likely callers' announcements, made ahead of time (calls/caller_voice_prep.dart).
  final callerVoices = CallerVoicePrep(
    store: store,
    mouth: jarvis,
    bridge: callBridge,
    isCharging: () async => (await phone.battery())?.charging ?? false,
    isBusy: () => session.active || calls.phase != CallFlowPhase.idle,
  );
  Battery().onBatteryStateChanged.listen((state) {
    if (state == BatteryState.charging) unawaited(callerVoices.run()); // charging → make up to 40
  });
  if (store.settings.callsByVoice) unawaited(calls.applySetting()); // the app is on screen now — allowed to start
  runApp(AppScope(store: store, session: session, calls: calls, child: const AerisApp()));

  // adb-started checks: `adb shell am start -n com.aeris.aeris_assistant/.MainActivity --es route /voicecheck`
  final startRoute = WidgetsBinding.instance.platformDispatcher.defaultRouteName;
  if (startRoute == '/voicecheck') unawaited(VoiceCheck.run(rate: store.settings.rate)); // features/settings/voice_check.dart
  if (startRoute.startsWith('/calltest')) {
    // `/calltest` or `/calltest?number=98765...` — a rehearsal once the voice is ready
    final number = Uri.parse(startRoute).queryParameters['number'] ?? '';
    unawaited(ModelStore.ensure().then(SpeechWorker.get).then((worker) => worker.warm()).then((_) => calls.rehearse(number: number)));
  }

  // First launch copies the on-device models out of the APK; later launches
  // just load them. Either way, warm them now so the first command is quick.
  // Then pre-make AERIS's most common replies (cached on disk) so they play
  // instantly — and re-make them whenever the speed setting changes.
  unawaited(ModelStore.ensure().then(SpeechWorker.get).then((w) => w.warm()).then((_) {
    return VoiceSpeedSync(store: store, mouth: jarvis, afterPremake: callerVoices.run).start();
  }).catchError((Object e) {
    debugPrint('model warm-up failed: $e');
  }));

  // The brain loads AFTER speech is ready (they'd fight for the CPU), and only
  // when it will be used: mode On + a model file present. It unloads itself
  // after 10 idle minutes, so an open app doesn't hold ~1.8 GB forever.
  unawaited(brain.load().then((_) async {
    if (!brain.enabled) return;
    await ModelStore.ensure().then(SpeechWorker.get).then((worker) => worker.warm());
    final ready = await brain.ensureReady(store.settings.lang);
    debugPrint('AERIS brain: ${ready ? brain.statusText.value : 'not loaded (${brain.statusText.value})'}');
  }).catchError((Object e) {
    debugPrint('brain warm-up failed: $e');
  }));
}

/// Edge-to-edge, light icons, portrait. Fire-and-forget: these calls are
/// answered by the screen, and a background start has none — awaiting them
/// there once stopped main() before the call assistant existed (2026-11-17).
void _styleSystemBars() {
  void ignoreNoScreen(Object error) => debugPrint('system bars not styled (no screen yet): $error');
  SystemChrome.setEnabledSystemUIMode(SystemUiMode.edgeToEdge).catchError(ignoreNoScreen);
  SystemChrome.setSystemUIOverlayStyle(const SystemUiOverlayStyle(
    statusBarColor: Colors.transparent,
    statusBarIconBrightness: Brightness.light,
    systemNavigationBarColor: Colors.transparent,
    systemNavigationBarIconBrightness: Brightness.light,
  ));
  SystemChrome.setPreferredOrientations([DeviceOrientation.portraitUp]).catchError(ignoreNoScreen);
}

class AerisApp extends StatelessWidget {
  const AerisApp({super.key});

  @override
  Widget build(BuildContext context) => MaterialApp(
        title: 'AERIS',
        debugShowCheckedModeBanner: false,
        theme: aerisTheme(),
        home: const RootGate(),
      );
}
