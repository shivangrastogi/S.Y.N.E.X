import 'package:aeris_mobile/core/logger.dart';
import 'package:aeris_mobile/design/theme.dart';
import 'package:aeris_mobile/ui/diagnostics_screen.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

Widget harness(AerisLog log, {int skills = 7, int messages = 0}) => MaterialApp(
      theme: AerisTheme.dark(),
      home: DiagnosticsScreen(
        log: log,
        skillCount: skills,
        messageCount: messages,
      ),
    );

void main() {
  group('AerisLog', () {
    test('returns newest first', () {
      final log = AerisLog();
      log.info('a', 'first');
      log.info('b', 'second');
      expect(log.entries.first.message, 'second');
      expect(log.entries.last.message, 'first');
    });

    test('is bounded, dropping the oldest', () {
      final log = AerisLog(capacity: 3);
      for (var i = 0; i < 10; i++) {
        log.debug('t', 'entry $i');
      }
      expect(log.length, 3);
      expect(log.entries.first.message, 'entry 9');
      expect(log.entries.last.message, 'entry 7');
    });

    test('stamps a zero-padded clock', () {
      final log = AerisLog();
      log.info('t', 'x');
      expect(log.entries.first.stamp, matches(RegExp(r'^\d{2}:\d{2}:\d{2}$')));
    });

    test('clear empties it', () {
      final log = AerisLog()..info('t', 'x');
      log.clear();
      expect(log.length, 0);
    });
  });

  group('DiagnosticsScreen', () {
    testWidgets('shows the counts', (tester) async {
      final log = AerisLog()
        ..info('router', 'started')
        ..warn('voice', 'no microphone');

      await tester.pumpWidget(harness(log, skills: 7, messages: 4));

      expect(find.text('SKILLS'), findsOneWidget);
      expect(find.text('7'), findsOneWidget);
      expect(find.text('4'), findsOneWidget); // messages
      expect(find.text('2'), findsOneWidget); // events
      expect(find.text('1'), findsOneWidget); // problems (the warn)
    });

    testWidgets('lists entries newest first with their level', (tester) async {
      final log = AerisLog()
        ..debug('skills', 'selected math')
        ..error('router', 'laptop failed');

      await tester.pumpWidget(harness(log));

      expect(find.textContaining('laptop failed'), findsOneWidget);
      expect(find.textContaining('selected math'), findsOneWidget);
      expect(find.text('ERROR'), findsOneWidget);
      expect(find.text('DEBUG'), findsOneWidget);
    });

    testWidgets('the problems filter hides debug and info', (tester) async {
      final log = AerisLog()
        ..debug('skills', 'selected math')
        ..info('store', 'restored')
        ..warn('voice', 'no microphone');

      await tester.pumpWidget(harness(log));
      expect(find.textContaining('selected math'), findsOneWidget);

      await tester.tap(find.byType(Switch));
      await tester.pumpAndSettle();

      expect(find.textContaining('selected math'), findsNothing);
      expect(find.textContaining('restored'), findsNothing);
      expect(find.textContaining('no microphone'), findsOneWidget);
    });

    testWidgets('says so when nothing has gone wrong', (tester) async {
      final log = AerisLog()..debug('skills', 'selected math');
      await tester.pumpWidget(harness(log));

      await tester.tap(find.byType(Switch));
      await tester.pumpAndSettle();

      expect(find.text('Nothing has gone wrong.'), findsOneWidget);
    });

    testWidgets('invites action when empty', (tester) async {
      await tester.pumpWidget(harness(AerisLog()));
      expect(find.textContaining('Ask A.E.R.I.S something'), findsOneWidget);
    });

    testWidgets('clearing empties the list', (tester) async {
      final log = AerisLog()..warn('voice', 'no microphone');
      await tester.pumpWidget(harness(log));

      await tester.tap(find.text('Clear'));
      await tester.pumpAndSettle();

      expect(find.textContaining('no microphone'), findsNothing);
      expect(log.length, 0);
    });

    testWidgets('updates live as new entries arrive', (tester) async {
      final log = AerisLog();
      await tester.pumpWidget(harness(log));
      expect(find.textContaining('late arrival'), findsNothing);

      log.error('router', 'late arrival');
      await tester.pumpAndSettle();

      expect(find.textContaining('late arrival'), findsOneWidget);
    });
  });
}
