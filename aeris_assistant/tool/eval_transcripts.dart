// Scores ASR transcripts by what matters: does AERIS do the same thing it
// would do with the perfect text? Usage:
//   dart run tool/eval_transcripts.dart results.json
import 'dart:convert';
import 'dart:io';

import 'package:aeris_assistant/brain/router.dart';
import 'package:aeris_assistant/voice/translit.dart';

void main(List<String> args) {
  final data = jsonDecode(File(args.first).readAsStringSync()) as Map<String, dynamic>;
  const r = Router();
  final now = DateTime(2026, 11, 16, 21, 4);
  String sig(Plan p) {
    final keys = ['hour', 'minute', 'seconds', 'on', 'to', 'app', 'value'];
    return '${p.tool}${[for (final k in keys) if (p.args.containsKey(k)) '$k=${p.args[k]}'].join(',')}';
  }

  final verbose = args.contains('-v');
  for (final e in data.entries) {
    final rows = (e.value['rows'] as List).cast<Map<String, dynamic>>();
    var ok = 0, toolOk = 0;
    final misses = <String>[];
    for (final row in rows) {
      final want = r.route(row['ref'] as String, now: now);
      final heard = cleanTranscript(row['hyp'] as String);
      final got = r.route(heard, now: now);
      if (got.tool == want.tool) toolOk++;
      if (sig(got) == sig(want)) {
        ok++;
      } else {
        misses.add('   ✗ "${row['ref']}" → heard "$heard" → ${sig(got)}');
      }
    }
    stdout.writeln('${e.key.padRight(20)} action ${'$ok/${rows.length}'.padLeft(5)}  '
        'tool ${'$toolOk/${rows.length}'.padLeft(5)}  RTF ${(e.value['rtf'] as num).toStringAsFixed(3)}');
    if (verbose) misses.forEach(stdout.writeln);
  }
}
