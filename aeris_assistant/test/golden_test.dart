import 'dart:io';

import 'package:aeris_assistant/brain/router.dart';
import 'package:flutter_test/flutter_test.dart';

/// Routing accuracy on test/data/golden_commands.tsv — real sentences and the
/// tool that must answer them. Prints the score and every miss; fails on any
/// miss, so a fix for one phrase can't silently break another.
///
///   flutter test test/golden_test.dart
void main() {
  test('golden commands route to the right tool', () {
    final lines = File('test/data/golden_commands.tsv').readAsLinesSync();
    final cases = [
      for (final line in lines)
        if (line.trim().isNotEmpty && !line.startsWith('#')) line.split('\t'),
    ];
    const router = Router();
    final now = DateTime(2026, 11, 17, 21, 0); // evening: "kal subah" alarms need no approval
    final misses = <String>[];
    for (final c in cases) {
      expect(c.length, 2, reason: 'bad line (needs one TAB): ${c.join('|')}');
      final plan = router.route(c[0], now: now);
      final got = plan.tool == 'search' && plan.args['fallback'] == true ? 'fallback' : plan.tool;
      if (got != c[1]) misses.add('  "${c[0]}" → $got (want ${c[1]})');
    }
    final score = (cases.length - misses.length) * 100 / cases.length;
    // ignore: avoid_print
    print('golden routing: ${cases.length - misses.length}/${cases.length} (${score.toStringAsFixed(1)}%)'
        '${misses.isEmpty ? '' : '\n${misses.join('\n')}'}');
    expect(misses, isEmpty);
  });
}
