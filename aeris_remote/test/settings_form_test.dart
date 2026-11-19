// Settings save behaviour: Save is enabled only when the form changed,
// the unsaved-changes bar appears, Save persists, and leaving with
// unsaved edits asks "Discard changes?".
import 'package:aeris_remote/assistant/cloud_brain.dart';
import 'package:aeris_remote/settings/settings_screen.dart';
import 'package:aeris_remote/ui/theme.dart';
import 'package:flutter/material.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';

const _key = 'AIzaSyD-test-key-0123456789abcdef';

Future<void> _open(WidgetTester t) async {
  await t.pumpWidget(MaterialApp(
    theme: A.theme(),
    home: Builder(
      builder: (c) => Scaffold(
        body: Center(
          child: TextButton(
            onPressed: () => Navigator.of(c).push(MaterialPageRoute(builder: (_) => const CloudAiPage())),
            child: const Text('open'),
          ),
        ),
      ),
    ),
  ));
  await t.tap(find.text('open'));
  await t.pumpAndSettle();
}

FilledButton _saveButton(WidgetTester t) =>
    t.widget<FilledButton>(find.widgetWithText(FilledButton, 'Save').first);

void main() {
  setUp(() => FlutterSecureStorage.setMockInitialValues({}));

  testWidgets('Save is disabled until something changes', (t) async {
    await _open(t);
    expect(_saveButton(t).onPressed, isNull);
    expect(find.text('Unsaved changes'), findsOneWidget); // present but hidden
    await t.enterText(find.byType(TextField).first, _key);
    await t.pumpAndSettle();
    expect(_saveButton(t).onPressed, isNotNull);
  });

  testWidgets('Save persists and clears the dirty state', (t) async {
    await _open(t);
    await t.enterText(find.byType(TextField).first, _key);
    await t.pumpAndSettle();
    await t.tap(find.widgetWithText(FilledButton, 'Save').first);
    await t.pumpAndSettle();
    expect(await CloudBrain.apiKey, _key);
    expect(find.text('Cloud AI settings saved'), findsOneWidget);
    expect(_saveButton(t).onPressed, isNull);
  });

  testWidgets('invalid key shows an error and is not saved', (t) async {
    await _open(t);
    await t.enterText(find.byType(TextField).first, 'not a key');
    await t.pumpAndSettle();
    expect(find.text('That doesn\'t look like a Gemini API key'), findsOneWidget);
    await t.tap(find.widgetWithText(FilledButton, 'Save').first);
    await t.pumpAndSettle();
    expect(await CloudBrain.apiKey, '');
  });

  testWidgets('back with unsaved edits asks first; Discard leaves', (t) async {
    await _open(t);
    await t.enterText(find.byType(TextField).first, _key);
    await t.pumpAndSettle();
    await t.binding.handlePopRoute();
    await t.pumpAndSettle();
    expect(find.text('Discard changes?'), findsOneWidget);
    await t.tap(find.text('Discard').last);
    await t.pumpAndSettle();
    expect(find.text('open'), findsOneWidget);
    expect(await CloudBrain.apiKey, '');
  });
}
