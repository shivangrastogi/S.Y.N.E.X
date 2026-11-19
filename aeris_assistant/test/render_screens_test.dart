// Renders every main screen to build/screens/*.png — a phone-free way to
// review the UI. Run:  AERIS_RENDER=1 flutter test test/render_screens_test.dart
import 'dart:async';
import 'dart:io';
import 'dart:ui' as ui;

import 'package:aeris_assistant/app/app.dart';
import 'package:aeris_assistant/app/scope.dart';
import 'package:aeris_assistant/brain/executor.dart';
import 'package:aeris_assistant/core/models.dart';
import 'package:aeris_assistant/core/store.dart';
import 'package:aeris_assistant/features/boot/boot_screen.dart';
import 'package:aeris_assistant/features/onboarding/onboarding_screen.dart';
import 'package:aeris_assistant/features/settings/settings_screen.dart';
import 'package:aeris_assistant/ui/theme.dart';
import 'package:aeris_assistant/voice/io.dart';
import 'package:aeris_assistant/voice/session.dart';
import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';

import 'fakes.dart';

final _skip = !Platform.environment.containsKey('AERIS_RENDER');

Future<void> _loadFonts() async {
  Future<void> load(String family, List<String> files) async {
    final l = FontLoader(family);
    for (final f in files) {
      l.addFont(Future.value(ByteData.view(File(f).readAsBytesSync().buffer)));
    }
    await l.load();
  }

  await load('Sora', [
    'assets/fonts/Sora-Light.ttf',
    'assets/fonts/Sora-Regular.ttf',
    'assets/fonts/Sora-Medium.ttf',
    'assets/fonts/Sora-SemiBold.ttf',
  ]);
  await load('Oxanium', ['assets/fonts/Oxanium-Variable.ttf']);
  await load('JetBrainsMono', ['assets/fonts/JetBrainsMono-Variable.ttf']);
  final flutterRoot = Platform.environment['FLUTTER_ROOT'] ?? r'D:\Flutter\flutter_windows_3.44.0-stable\flutter';
  await load('MaterialIcons', ['$flutterRoot/bin/cache/artifacts/material_fonts/materialicons-regular.otf']);
}

/// A mouth that never finishes, so the "speaking" state can be captured.
class _HoldMouth implements Mouth {
  @override
  String get engineName => 'hold';
  @override
  Future<void> configure({required String language, required double rate, String? voice, SpeechOutput output = SpeechOutput.normal}) async {}
  @override
  Future<bool> speak(String text, {void Function(int start, int end)? onWord}) => Completer<bool>().future;
  @override
  Future<void> stop() async {}
  @override
  Future<int> prepare(Iterable<String> texts) async => 0;
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  final messenger = TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger;
  messenger.setMockMethodCallHandler(SystemChannels.platform, (_) async => null);
  // permission_handler → "granted"
  messenger.setMockMethodCallHandler(const MethodChannel('flutter.baseflow.com/permissions/methods'), (call) async {
    if (call.method == 'checkPermissionStatus') return 1;
    if (call.method == 'requestPermissions') return <int, int>{};
    return null;
  });

  late Store store;

  Store seeded() {
    final s = Store.memory()..settings = const Settings(name: 'Shivang', onboarded: true);
    s.protocols.addAll(Store.defaultProtocols());
    final now = DateTime.now();
    final items = [
      ('kal subah 6:30 ka alarm laga do', 'alarm', '6:30 AM ka alarm laga diya.', 2, TurnStatus.ok, 38),
      ('Ravi ko WhatsApp karo ki main late hoon', 'message', 'Message ready hai — bas send dabaiye.', 14, TurnStatus.ok, 412),
      ('battery kitni hai', 'battery', 'Battery 82% hai.', 41, TurnStatus.ok, 21),
      ('Zoya ko call karo', 'call', 'Contacts mein "zoya" nahi mila.', 95, TurnStatus.failed, 64),
      ('10 minute ka timer', 'timer', '10 minute ka timer shuru.', 60 * 26, TurnStatus.ok, 30),
    ];
    for (final (said, tool, reply, minsAgo, st, ms) in items.reversed) {
      s.addActivity(ActivityEntry(
        id: Store.newId(),
        at: now.subtract(Duration(minutes: minsAgo)),
        said: said,
        tool: tool,
        args: const {},
        reply: reply,
        status: st,
        latencyMs: ms,
      ));
    }
    s.addMemory('Wifi password is tiger123');
    s.addMemory('Mummy ki dawai raat 9 baje');
    s.addMemory('Car parked at B2, pillar 14');
    return s;
  }

  Future<void> shot(WidgetTester tester, String name, Widget child, {VoiceSession? session, Future<void> Function()? before}) async {
    tester.view.physicalSize = const Size(1080, 2400);
    tester.view.devicePixelRatio = 2.625;
    addTearDown(tester.view.reset);
    final s = session ??
        VoiceSession(store: store, ears: FakeEars([]), mouth: FakeMouth(), exec: Executor(FakePhone(), store));
    final key = GlobalKey();
    await tester.pumpWidget(RepaintBoundary(
      key: key,
      child: AppScope(
        store: store,
        session: s,
        child: MaterialApp(debugShowCheckedModeBanner: false, theme: aerisTheme(), home: child),
      ),
    ));
    if (before != null) await before();
    for (var i = 0; i < 40; i++) {
      await tester.pump(const Duration(milliseconds: 50));
    }
    await tester.runAsync(() async {
      final boundary = key.currentContext!.findRenderObject()! as RenderRepaintBoundary;
      final img = await boundary.toImage(pixelRatio: 1.5);
      final bytes = await img.toByteData(format: ui.ImageByteFormat.png);
      Directory('build/screens').createSync(recursive: true);
      File('build/screens/$name.png').writeAsBytesSync(bytes!.buffer.asUint8List());
    });
    await tester.pumpWidget(const SizedBox());
    await tester.pump(const Duration(seconds: 1));
  }

  setUpAll(_loadFonts);
  setUp(() => store = seeded());

  testWidgets('boot', (t) async {
    await shot(t, '00_boot', BootScreen(firstRun: true, onDone: () {}));
  }, skip: _skip);

  testWidgets('onboarding', (t) async {
    store.settings = const Settings();
    await shot(t, '01_onboarding', const OnboardingScreen());
  }, skip: _skip);

  testWidgets('home', (t) async {
    await shot(t, '10_home', const Shell());
  }, skip: _skip);

  testWidgets('voice listening', (t) async {
    final s = VoiceSession(store: store, ears: FakeEars([]), mouth: FakeMouth(), exec: Executor(FakePhone(), store));
    await shot(t, '20_voice_listening', const Shell(), session: s, before: () async {
      unawaited(s.start());
      await t.pump();
      s.partial = 'Ravi ko WhatsApp karo ki main late';
      s.level.value = 0.75;
      // ignore: invalid_use_of_protected_member, invalid_use_of_visible_for_testing_member
      s.notifyListeners();
    });
  }, skip: _skip);

  testWidgets('voice speaking', (t) async {
    final s = VoiceSession(store: store, ears: FakeEars([]), mouth: _HoldMouth(), exec: Executor(FakePhone(), store));
    await shot(t, '21_voice_speaking', const Shell(), session: s, before: () async {
      unawaited(s.submitText('kal subah 6:30 ka alarm laga do'));
      await t.pump(const Duration(milliseconds: 100));
      s.spokenRange.value = (5, 7);
    });
  }, skip: _skip);

  testWidgets('voice approval', (t) async {
    final s = VoiceSession(store: store, ears: FakeEars([]), mouth: FakeMouth(), exec: Executor(FakePhone(), store));
    await shot(t, '22_voice_approval', const Shell(), session: s, before: () async {
      unawaited(s.submitText('Ravi ko WhatsApp karo ki main 10 minute late hoon'));
      await t.pump(const Duration(milliseconds: 100));
    });
  }, skip: _skip);

  for (final (i, name) in const [(1, '30_log'), (2, '31_memory'), (3, '32_protocols')]) {
    testWidgets(name, (t) async {
      await shot(t, name, const Shell(), before: () async {
        await t.pump(const Duration(milliseconds: 600));
        await t.tap(find.byType(InkWell).at(_navIndex(t, i)));
        await t.pump();
      });
    }, skip: _skip);
  }

  testWidgets('settings', (t) async {
    await shot(t, '40_settings', const SettingsScreen());
  }, skip: _skip);
}

/// Index of the i-th bottom-nav InkWell (they're the last four on screen).
int _navIndex(WidgetTester t, int i) => find.byType(InkWell).evaluate().length - 4 + i;
