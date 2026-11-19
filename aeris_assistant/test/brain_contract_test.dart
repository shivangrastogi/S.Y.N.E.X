// Pins the Dart brain (contract / prompt / grammar) to the Python training
// pipeline. Fixtures: `py -3.10 -m scripts.sync_app` in aeris_brain/.
import 'dart:convert';
import 'dart:io';

import 'package:aeris_assistant/brain/llm/contract.dart';
import 'package:aeris_assistant/brain/llm/grammar.dart';
import 'package:aeris_assistant/brain/llm/prompt.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  final tools = parseTools(File('assets/brain/tools.json').readAsStringSync());
  final golden = jsonDecode(
      File('test/fixtures/brain_golden.json').readAsStringSync()) as Map<String, dynamic>;

  test('tools.json is the trained registry', () {
    expect(tools.length, 37);
    expect(tools.keys.first, 'flashlight');
    expect(tools['send_message']!.oneOf, ['contact', 'number']);
  });

  group('prompt is byte-identical to training', () {
    for (final (i, p) in (golden['prompts'] as List).indexed) {
      test('system prompt #$i', () {
        final sel = [for (final n in p['tools'] as List) tools[n]!];
        final text = systemPrompt(sel,
            lang: p['lang'] as String,
            now: p['now'] as String?,
            memory: (p['memory'] as List?)?.cast<String>());
        expect(text, p['text']);
      });
    }
    for (final (i, c) in (golden['chats'] as List).indexed) {
      test('Qwen3 chat prompt #$i', () {
        final turns = [
          for (final t in c['turns'] as List)
            (role: t[0] as String, content: t[1] as String)
        ];
        expect(qwenPrompt(c['system'] as String, turns), c['prompt']);
      });
    }
  });

  test('the cached prefix really is a prefix of every turn\'s prompt', () {
    final all = tools.values.toList();
    final fixed = basePrompt(all, lang: 'match');
    final turnPrompt = qwenPrompt(
        systemPrompt(all, lang: 'match', now: 'Monday 17 November 2026, 09:05', memory: ['meri car B2 mein hai']),
        [(role: 'user', content: 'car kahan hai?')]);
    expect(turnPrompt.startsWith(cachedPrefix(fixed)), isTrue);
  });

  test('canonical JSON matches Python', () {
    for (final c in golden['canonical'] as List) {
      expect(canonical((c['input'] as Map).cast<String, dynamic>(), tools), c['canonical']);
    }
  });

  test('validate agrees with Python on every case', () {
    for (final v in golden['validate'] as List) {
      final errs = validate(v['output'], tools,
          userText: v['user_text'] as String?, grounded: v['user_text'] != null);
      expect(errs.length, (v['errors'] as List).length, reason: '${v['output']} → $errs');
    }
  });

  test('parseOutput tolerates fences and trailing junk', () {
    expect(parseOutput('```json\n{"type":"reply","text":"hi"}\n```')!['text'], 'hi');
    expect(parseOutput(' {"type":"reply","text":"a"}<|im_end|>')!['type'], 'reply');
    expect(parseOutput('no json here'), isNull);
    expect(parseOutput('{"type": broken'), isNull);
  });

  group('grammar', () {
    final all = contractGrammar(tools.values.toList());
    final m = GrammarMatcher(all);

    test('accepts every golden canonical target', () {
      for (final c in golden['canonical'] as List) {
        expect(m.accepts(c['canonical'] as String), isTrue, reason: c['canonical']);
      }
    });

    test('accepts optional-arg subsets in schema order', () {
      for (final s in [
        '{"type":"tool_call","calls":[{"name":"call","args":{"contact":"Ravi"}}]}',
        '{"type":"tool_call","calls":[{"name":"call","args":{"number":"7300978845","video":true}}]}',
        '{"type":"tool_call","calls":[{"name":"battery_status","args":{}}]}',
        '{"type":"tool_call","calls":[{"name":"volume","args":{"action":"set","level":-0}}]}',
        '{"type":"ask","text":"Kisko?"}',
        '{"type":"reply","text":"line\\nbreak \\"q\\" \\u00e9 नमस्ते"}',
      ]) {
        expect(m.accepts(s), isTrue, reason: s);
      }
    });

    test('rejects malformed or off-contract output', () {
      for (final s in [
        '{"type":"tool_call","calls":[{"name":"flashlight","args":{"state":"dim"}}]}',
        '{"type":"tool_call","calls":[{"name":"set_alarm","args":{"label":"gym"}}]}', // time required
        '{"type":"tool_call","calls":[{"name":"set_alarm","args":{"label":"x","time":"7"}}]}', // order
        '{"type":"tool_call","calls":[{"name":"teleport","args":{}}]}',
        '{"type":"tool_call","calls":[]}',
        '{"type":"reply","text":""}',
        '{"type":"plan","goal":"g","steps":["only one"]}',
        '{"type":"escalate","reason":"bored","query":"q"}',
        '{"type":"reply","text":"hi"} trailing',
        '{"type": "reply", "text": "spaced"}',
      ]) {
        expect(m.accepts(s), isFalse, reason: s);
      }
    });

    test('offered subset limits tools and pending', () {
      final g = GrammarMatcher(contractGrammar([tools['flashlight']!]));
      expect(g.accepts('{"type":"tool_call","calls":[{"name":"flashlight","args":{"state":"on"}}]}'), isTrue);
      expect(g.accepts('{"type":"tool_call","calls":[{"name":"call","args":{"contact":"Ravi"}}]}'), isFalse);
      expect(g.accepts('{"type":"ask","text":"x","pending":"call"}'), isFalse);
    });

    test('GBNF text is well-formed', () {
      final gbnf = all.toGbnf();
      final names = RegExp(r'^([a-z0-9-]+) ::= ', multiLine: true)
          .allMatches(gbnf)
          .map((x) => x.group(1)!)
          .toSet();
      expect(names.first, 'root');
      expect(names.every((n) => !n.contains('_')), isTrue);
      // every referenced rule is defined
      final body = gbnf.replaceAll(RegExp(r'"(?:[^"\\]|\\.)*"'), '').replaceAll(RegExp(r'\[[^\]]*\]'), '');
      for (final ref in RegExp(r'(?<![\w-])([a-z][a-z0-9-]*)(?![\w-]| ::=)').allMatches(body)) {
        expect(names, contains(ref.group(1)), reason: ref.group(1));
      }
    });
  });
}
