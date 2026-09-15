import 'package:aeris_mobile/brain/router.dart';
import 'package:aeris_mobile/design/theme.dart';
import 'package:aeris_mobile/skills/builtin/builtins.dart';
import 'package:aeris_mobile/state/app_settings.dart';
import 'package:aeris_mobile/state/conversation.dart';
import 'package:aeris_mobile/store/settings_store.dart';
import 'package:aeris_mobile/ui/chat_screen.dart';
import 'package:aeris_mobile/ui/settings_screen.dart';
import 'package:aeris_mobile/voice/voice.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

Widget chat(AppSettings? settings) {
  final skills = defaultSkills();
  return MaterialApp(
    theme: AerisTheme.light(),
    darkTheme: AerisTheme.dark(),
    themeMode: settings?.themeMode ?? ThemeMode.dark,
    home: ChatScreen(
      conversation: Conversation(BrainRouter(skills: skills)),
      skills: skills,
      voiceIn: SilentVoiceIn(),
      voiceOut: SilentVoiceOut(),
      settings: settings,
    ),
  );
}

void main() {
  group('AppSettings', () {
    test('defaults to following the system', () {
      expect(AppSettings().themeMode, ThemeMode.system);
    });

    test('notifies and persists on change', () async {
      final store = MemorySettingsStore();
      final settings = AppSettings(store: store);
      var notified = 0;
      settings.addListener(() => notified++);

      settings.setThemeMode(ThemeMode.light);

      expect(settings.themeMode, ThemeMode.light);
      expect(notified, 1);
      await Future<void>.delayed(Duration.zero);
      expect(await store.loadThemeMode(), ThemeMode.light);
    });

    test('setting the same value does not notify', () {
      final settings = AppSettings();
      var notified = 0;
      settings.addListener(() => notified++);
      settings.setThemeMode(ThemeMode.system);
      expect(notified, 0);
    });

    test('restores a saved choice', () async {
      final store = MemorySettingsStore();
      await store.saveThemeMode(ThemeMode.dark);

      final settings = AppSettings(store: store);
      await settings.restore();

      expect(settings.themeMode, ThemeMode.dark);
    });

    test('restoring with nothing saved keeps the default', () async {
      final settings = AppSettings(store: MemorySettingsStore());
      await settings.restore();
      expect(settings.themeMode, ThemeMode.system);
    });
  });

  group('SettingsScreen', () {
    testWidgets('shows the current choice and changes it', (tester) async {
      final settings = AppSettings(store: MemorySettingsStore());
      await tester.pumpWidget(MaterialApp(
        theme: AerisTheme.dark(),
        home: SettingsScreen(settings: settings),
      ));

      expect(find.text('Appearance'), findsOneWidget);
      expect(
        tester
            .widget<SegmentedButton<ThemeMode>>(
                find.byType(SegmentedButton<ThemeMode>))
            .selected,
        {ThemeMode.system},
      );

      await tester.tap(find.text('Light'));
      await tester.pumpAndSettle();

      expect(settings.themeMode, ThemeMode.light);
    });

    testWidgets('is honest that the laptop tier does not exist yet',
        (tester) async {
      await tester.pumpWidget(MaterialApp(
        theme: AerisTheme.dark(),
        home: SettingsScreen(settings: AppSettings()),
      ));

      expect(find.text('Laptop — not connected'), findsOneWidget);
      expect(find.textContaining('not built yet'), findsOneWidget);
    });
  });

  group('reaching settings from the chat screen', () {
    testWidgets('the button opens it', (tester) async {
      await tester.pumpWidget(chat(AppSettings(store: MemorySettingsStore())));

      await tester.tap(find.byIcon(Icons.tune));
      await tester.pumpAndSettle();

      expect(find.text('SETTINGS'), findsOneWidget);
      expect(find.text('Appearance'), findsOneWidget);
    });

    testWidgets('the button is hidden when there is nothing to configure',
        (tester) async {
      await tester.pumpWidget(chat(null));
      expect(find.byIcon(Icons.tune), findsNothing);
      // Diagnostics stays available either way.
      expect(find.byIcon(Icons.monitor_heart_outlined), findsOneWidget);
    });
  });

  group('light theme', () {
    testWidgets('renders the chat screen with light tokens', (tester) async {
      final settings = AppSettings(store: MemorySettingsStore())
        ..setThemeMode(ThemeMode.light);
      await tester.pumpWidget(chat(settings));
      await tester.pumpAndSettle();

      final ctx = tester.element(find.byType(ChatScreen));
      expect(Theme.of(ctx).scaffoldBackgroundColor, AerisPalette.light.ground);
      // The palette extension must resolve to light too, or widgets reading
      // through it would keep painting dark on a light ground.
      expect(AerisPalette.of(ctx).ink, AerisPalette.light.ink);
    });

    test('light and dark differ on every token that carries meaning', () {
      const l = AerisPalette.light;
      const d = AerisPalette.dark;
      expect(l.ground, isNot(d.ground));
      expect(l.ink, isNot(d.ink));
      expect(l.tierDevice, isNot(d.tierDevice));
      expect(l.tierLaptop, isNot(d.tierLaptop));
      expect(l.tierCloud, isNot(d.tierCloud));
    });
  });
}
