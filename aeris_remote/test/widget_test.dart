// Minimal smoke test. The default template test referenced a non-existent
// `MyApp` (counter app); AERIS Remote has its own root, so we keep a trivial
// build check here instead.
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  testWidgets('renders a MaterialApp without throwing', (tester) async {
    await tester.pumpWidget(
      const MaterialApp(home: Scaffold(body: Text('AERIS'))),
    );
    expect(find.text('AERIS'), findsOneWidget);
  });
}
