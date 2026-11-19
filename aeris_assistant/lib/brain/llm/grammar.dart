// GBNF grammar for llama.cpp constrained decoding: the model CANNOT emit
// anything but a canonical contract object over the offered tools — no
// stray text, no unknown tool, no `"state":"dim"`, keys in trained order.
//
// The grammar is built as a small AST first. `toGbnf()` prints it for
// llama.cpp; `GrammarMatcher` runs the very same AST in pure Dart, so tests
// prove every canonical training target is accepted (and junk rejected)
// without a phone. Value checks the grammar can't express (int ranges,
// one_of, span grounding) stay in validate() after decoding.
import 'dart:convert';

import 'contract.dart';

sealed class G {
  const G();
}

class Lit extends G {
  final String s;
  const Lit(this.s);
}

class Seq extends G {
  final List<G> items;
  const Seq(this.items);
}

class Alt extends G {
  final List<G> options;
  const Alt(this.options);
}

class Ref extends G {
  final String name;
  const Ref(this.name);
}

/// min..max repetitions (max null = unbounded).
class Rep extends G {
  final G g;
  final int min;
  final int? max;
  const Rep(this.g, this.min, [this.max]);
}

/// A character class: GBNF body (between the brackets) + the same test.
class Chars extends G {
  final String gbnf;
  final bool Function(int code) test;
  const Chars(this.gbnf, this.test);
}

class Grammar {
  final Map<String, G> rules; // 'root' first
  const Grammar(this.rules);

  String toGbnf() => [
        for (final e in rules.entries) '${e.key} ::= ${_emit(e.value, top: true)}'
      ].join('\n');

  static String _emit(G g, {bool top = false}) => switch (g) {
        Lit(:final s) => _lit(s),
        Ref(:final name) => name,
        Chars(:final gbnf) => '[$gbnf]',
        Seq(:final items) => items.isEmpty
            ? '""'
            : (top ? items.map(_emit).join(' ') : '(${items.map(_emit).join(' ')})'),
        Alt(:final options) => top
            ? options.map(_emit).join(' | ')
            : '(${options.map(_emit).join(' | ')})',
        Rep(:final g, :final min, :final max) => _rep(_emit(g), min, max),
      };

  static String _rep(String inner, int min, int? max) {
    if (min == 0 && max == 1) return '$inner?';
    if (min == 0 && max == null) return '$inner*';
    if (min == 1 && max == null) return '$inner+';
    return '$inner{$min,${max ?? ''}}';
  }

  static String _lit(String s) {
    final b = StringBuffer('"');
    for (final r in s.runes) {
      switch (r) {
        case 0x22:
          b.write(r'\"');
        case 0x5c:
          b.write(r'\\');
        case 0x0a:
          b.write(r'\n');
        default:
          b.writeCharCode(r);
      }
    }
    b.write('"');
    return b.toString();
  }
}

/// Backtracking matcher over the AST (tests only — fine for short JSON).
class GrammarMatcher {
  final Grammar grammar;
  GrammarMatcher(this.grammar);

  bool accepts(String text) {
    final runes = text.runes.toList();
    return _m(grammar.rules['root']!, runes, 0).contains(runes.length);
  }

  Set<int> _m(G g, List<int> s, int pos) {
    switch (g) {
      case Lit(s: final str):
        final lit = str.runes.toList();
        if (pos + lit.length > s.length) return const {};
        for (var i = 0; i < lit.length; i++) {
          if (s[pos + i] != lit[i]) return const {};
        }
        return {pos + lit.length};
      case Chars(:final test):
        return pos < s.length && test(s[pos]) ? {pos + 1} : const {};
      case Ref(:final name):
        return _m(grammar.rules[name]!, s, pos);
      case Seq(:final items):
        var cur = {pos};
        for (final it in items) {
          final next = <int>{};
          for (final p in cur) {
            next.addAll(_m(it, s, p));
          }
          if (next.isEmpty) return const {};
          cur = next;
        }
        return cur;
      case Alt(:final options):
        return {for (final o in options) ..._m(o, s, pos)};
      case Rep(g: final inner, :final min, :final max):
        var cur = {pos};
        final out = <int>{if (min == 0) pos};
        for (var n = 1; max == null || n <= max; n++) {
          final next = <int>{};
          for (final p in cur) {
            next.addAll(_m(inner, s, p).where((q) => q > p));
          }
          if (next.isEmpty) break;
          if (n >= min) out.addAll(next);
          cur = next;
        }
        return out;
    }
  }
}

String _ruleName(String tool) => 'call-${tool.replaceAll('_', '-')}';

Lit _key(String k, {bool comma = false}) => Lit('${comma ? ',' : ''}"$k":');

Lit _jsonStr(String v) => Lit(jsonEncode(v));

G _value(ToolParam p) => switch (p.type) {
      'enum' => Alt([for (final v in p.values) _jsonStr(v)]),
      'integer' => const Ref('int'),
      'number' => const Ref('num'),
      'boolean' => const Ref('bool'),
      'string' => const Ref('str'),
      _ => const Alt([Ref('str'), Ref('num'), Ref('bool')]),
    };

/// Args object body: any order-preserving subset of the params that keeps
/// every required one. `rest(i, first)` = params i.. where `first` says no
/// pair has been written yet (so no leading comma).
G _argsBody(ToolSpec t, Map<String, G> rules) {
  final ps = t.params.values.toList();
  final base = _ruleName(t.name);
  String name(int i, bool first) => '$base-${first ? 'f' : 'r'}$i';
  for (var i = ps.length; i >= 0; i--) {
    for (final first in [true, false]) {
      if (i == ps.length) {
        rules[name(i, first)] = const Seq([]);
        continue;
      }
      final p = ps[i];
      final take = Seq([_key(p.name, comma: !first), _value(p), Ref(name(i + 1, false))]);
      final skip = Ref(name(i + 1, first));
      rules[name(i, first)] = t.required.contains(p.name) ? take : Alt([take, skip]);
    }
  }
  return Ref(name(0, true));
}

/// Grammar for the contract restricted to [tools] (the offered ones).
Grammar contractGrammar(List<ToolSpec> tools) {
  final rules = <String, G>{};
  final variants = <G>[];
  if (tools.isNotEmpty) {
    variants.add(const Seq([Lit('"tool_call","calls":['), Ref('call'),
      Rep(Seq([Lit(','), Ref('call')]), 0), Lit(']}')]));
  }
  variants.addAll([
    Seq([
      const Lit('"ask","text":'),
      const Ref('str'),
      if (tools.isNotEmpty)
        Rep(Seq([const Lit(',"pending":'), Alt([for (final t in tools) _jsonStr(t.name)])]), 0, 1),
      const Lit('}'),
    ]),
    const Seq([Lit('"reply","text":'), Ref('str'), Lit('}')]),
    const Seq([Lit('"plan","goal":'), Ref('str'), Lit(',"steps":['), Ref('str'),
      Rep(Seq([Lit(','), Ref('str')]), 1), Lit(']}')]),
    Seq([
      const Lit('"escalate","reason":'),
      Alt([for (final r in escalateReasons) _jsonStr(r)]),
      const Lit(',"query":'),
      const Ref('str'),
      const Lit('}'),
    ]),
  ]);
  rules['root'] = Seq([const Lit('{"type":'), Alt(variants)]);
  if (tools.isNotEmpty) {
    rules['call'] = Alt([for (final t in tools) Ref(_ruleName(t.name))]);
  }
  for (final t in tools) {
    final body = <String, G>{};
    final args = _argsBody(t, body);
    rules[_ruleName(t.name)] =
        Seq([Lit('{"name":"${t.name}","args":{'), args, const Lit('}}')]);
    rules.addAll(Map.fromEntries(body.entries.toList().reversed));
  }
  rules['str'] = const Seq([Lit('"'), Rep(Ref('chr'), 1), Lit('"')]);
  rules['chr'] = Alt([
    Chars(r'^"\\\x00-\x1f', (c) => c != 0x22 && c != 0x5c && c >= 0x20),
    Seq([
      const Lit('\\'),
      Alt([
        Chars(r'"\\/bfnrt', (c) => '"\\/bfnrt'.codeUnits.contains(c)),
        Seq([const Lit('u'), for (var i = 0; i < 4; i++) Chars('0-9a-fA-F', _isHex)]),
      ]),
    ]),
  ]);
  rules['int'] = Seq([
    const Rep(Lit('-'), 0, 1),
    Alt([const Lit('0'), Seq([Chars('1-9', (c) => c >= 0x31 && c <= 0x39), Rep(Chars('0-9', _isDigit), 0, 9)])]),
  ]);
  rules['num'] = Seq([const Ref('int'), Rep(Seq([const Lit('.'), Rep(Chars('0-9', _isDigit), 1)]), 0, 1)]);
  rules['bool'] = const Alt([Lit('true'), Lit('false')]);
  return Grammar(rules);
}

bool _isDigit(int c) => c >= 0x30 && c <= 0x39;
bool _isHex(int c) => _isDigit(c) || (c >= 0x41 && c <= 0x46) || (c >= 0x61 && c <= 0x66);
