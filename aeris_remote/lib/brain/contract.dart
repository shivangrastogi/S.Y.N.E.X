// The on-device brain's output contract — a port of aeris_brain/brain/
// contract.py. Every brain turn is ONE JSON object of five types:
//
//   {"type":"tool_call","calls":[{"name":"set_alarm","args":{"time":"7 am"}}]}
//   {"type":"ask","text":"What should I tell Ravi?","pending":"send_message"}
//   {"type":"reply","text":"I'm good, thanks!"}
//   {"type":"plan","goal":"...","steps":["...","..."]}
//   {"type":"escalate","reason":"live_info","query":"aaj ka weather"}
//
// String args are SPANS copied from what the user said ("shaam 6 baje",
// "Ravi"); the executor normalises them with the existing phone parsers.
// test/brain_contract_test.dart pins this file to the Python original via
// golden fixtures written by `py -3.10 -m scripts.sync_app`.
import 'dart:convert';

const contractTypes = ['tool_call', 'ask', 'reply', 'plan', 'escalate'];
const escalateReasons = ['knowledge', 'live_info', 'complex', 'no_tool'];

class ToolParam {
  final String name;
  final String type; // enum | integer | boolean | number | string | any
  final List<String> values;
  final int? min, max;
  final String? hint;
  const ToolParam(this.name, this.type,
      {this.values = const [], this.min, this.max, this.hint});
}

class ToolSpec {
  final String name;
  final String description;
  final bool implemented;
  final bool confirm;
  final Map<String, ToolParam> params; // declaration order
  final List<String> required;
  final List<String> oneOf;
  const ToolSpec(this.name, this.description,
      {this.implemented = false,
      this.confirm = false,
      this.params = const {},
      this.required = const [],
      this.oneOf = const []});

  factory ToolSpec.fromJson(Map<String, dynamic> j) {
    final params = <String, ToolParam>{};
    (j['params'] as Map<String, dynamic>? ?? {}).forEach((k, v) {
      final p = v as Map<String, dynamic>;
      params[k] = ToolParam(k, p['type'] as String,
          values: [for (final x in (p['values'] as List? ?? [])) '$x'],
          min: p['min'] as int?,
          max: p['max'] as int?,
          hint: p['hint'] as String?);
    });
    return ToolSpec(j['name'] as String, j['description'] as String,
        implemented: j['implemented'] == true,
        confirm: j['confirm'] == true,
        params: params,
        required: [for (final x in (j['required'] as List? ?? [])) '$x'],
        oneOf: [for (final x in (j['one_of'] as List? ?? [])) '$x']);
  }
}

/// name → spec, in tools.json order (the order prompts list them in).
Map<String, ToolSpec> parseTools(String toolsJson) {
  final data = jsonDecode(toolsJson) as Map<String, dynamic>;
  return {
    for (final t in data['tools'] as List)
      (t as Map<String, dynamic>)['name'] as String: ToolSpec.fromJson(t)
  };
}

/// Stable compact JSON — the exact string the model was trained to emit.
/// `type` first, then contract order; args in the tool's parameter order.
String canonical(Map<String, dynamic> obj, [Map<String, ToolSpec>? tools]) {
  const order = ['type', 'calls', 'reason', 'query', 'goal', 'steps', 'text', 'pending'];
  final out = <String, dynamic>{
    for (final k in order)
      if (obj.containsKey(k)) k: obj[k]
  };
  for (final e in obj.entries) {
    out.putIfAbsent(e.key, () => e.value);
  }
  if (tools != null && out['calls'] is List) {
    out['calls'] = [
      for (final c in out['calls'] as List) orderArgs(c as Map<String, dynamic>, tools)
    ];
  }
  return jsonEncode(out);
}

Map<String, dynamic> orderArgs(Map<String, dynamic> call, Map<String, ToolSpec> tools) {
  final spec = tools[call['name']];
  final args = (call['args'] as Map?)?.cast<String, dynamic>() ?? {};
  if (spec == null) return call;
  final ordered = <String, dynamic>{
    for (final k in spec.params.keys)
      if (args.containsKey(k)) k: args[k]
  };
  for (final e in args.entries) {
    ordered.putIfAbsent(e.key, () => e.value);
  }
  return {'name': call['name'], 'args': ordered};
}

final _ws = RegExp(r'\s+');

/// Lowercase, collapse spaces, strip punctuation at the edges.
String normText(String s) {
  var t = s.toLowerCase().replaceAll(_ws, ' ');
  const edge = ' .,!?;:\'"';
  var a = 0, b = t.length;
  while (a < b && edge.contains(t[a])) {
    a++;
  }
  while (b > a && edge.contains(t[b - 1])) {
    b--;
  }
  return t.substring(a, b);
}

/// Problems with [out] (empty = valid). [grounded]: string args must appear
/// in [userText] — the check that stops a hallucinated name from acting.
List<String> validate(Object? out, Map<String, ToolSpec> tools,
    {Set<String>? allowed, String? userText, bool grounded = false}) {
  if (out is! Map) return ['output is not an object'];
  final t = out['type'];
  if (!contractTypes.contains(t)) return ['unknown type $t'];
  final errs = <String>[];
  void needStr(String key) {
    final v = out[key];
    if (v is! String || v.trim().isEmpty) errs.add("$t: '$key' must be a non-empty string");
  }

  switch (t) {
    case 'tool_call':
      final calls = out['calls'];
      if (calls is! List || calls.isEmpty) {
        return ["tool_call: 'calls' must be a non-empty list"];
      }
      for (final c in calls) {
        errs.addAll(_validateCall(c, tools, allowed, userText, grounded));
      }
    case 'ask':
      needStr('text');
      final p = out['pending'];
      if (p != null && !tools.containsKey(p)) errs.add('ask: unknown pending tool $p');
    case 'reply':
      needStr('text');
    case 'plan':
      needStr('goal');
      final steps = out['steps'];
      if (steps is! List ||
          steps.length < 2 ||
          !steps.every((s) => s is String && s.trim().isNotEmpty)) {
        errs.add("plan: 'steps' must be a list of 2+ non-empty strings");
      }
    case 'escalate':
      needStr('query');
      if (!escalateReasons.contains(out['reason'])) {
        errs.add('escalate: reason must be one of $escalateReasons');
      }
  }
  return errs;
}

List<String> _validateCall(Object? c, Map<String, ToolSpec> tools,
    Set<String>? allowed, String? userText, bool grounded) {
  if (c is! Map || c['name'] is! String) return ["call: needs a string 'name'"];
  final name = c['name'] as String;
  final spec = tools[name];
  if (spec == null) return ['call: unknown tool $name'];
  if (allowed != null && !allowed.contains(name)) return ['call: tool $name was not offered'];
  final args = c['args'] ?? const {};
  if (args is! Map) return ["$name: 'args' must be an object"];
  final errs = <String>[];
  args.forEach((k, v) {
    final p = spec.params[k];
    if (p == null) {
      errs.add('$name: unknown arg $k');
      return;
    }
    switch (p.type) {
      case 'enum':
        if (!p.values.contains(v)) errs.add('$name.$k: $v not in ${p.values}');
      case 'integer':
        if (v is! int) {
          errs.add('$name.$k: must be an integer');
        } else if ((p.min != null && v < p.min!) || (p.max != null && v > p.max!)) {
          errs.add('$name.$k: $v out of range');
        }
      case 'boolean':
        if (v is! bool) errs.add('$name.$k: must be true/false');
      case 'number':
        if (v is! num) errs.add('$name.$k: must be a number');
      case 'any':
        break;
      default: // string span
        if (v is! String || v.trim().isEmpty) {
          errs.add('$name.$k: must be a non-empty string');
        } else if (grounded && userText != null &&
            !normText(userText).contains(normText(v))) {
          errs.add("$name.$k: '$v' is not in the user's words");
        }
    }
  });
  for (final k in spec.required) {
    if (!args.containsKey(k)) errs.add("$name: missing required '$k'");
  }
  if (spec.oneOf.isNotEmpty && !spec.oneOf.any(args.containsKey)) {
    errs.add('$name: needs one of ${spec.oneOf}');
  }
  return errs;
}

/// Model text → contract object, or null if it isn't a JSON object.
/// Tolerates whitespace, code fences and trailing junk after the object.
Map<String, dynamic>? parseOutput(String text) {
  var s = text.trim();
  if (s.startsWith('```')) {
    final i = s.indexOf('{');
    if (i < 0) return null;
    s = s.substring(i);
  }
  final a = s.indexOf('{'), b = s.lastIndexOf('}');
  if (a < 0 || b <= a) return null;
  try {
    final v = jsonDecode(s.substring(a, b + 1));
    return v is Map<String, dynamic> ? v : null;
  } on FormatException {
    return null;
  }
}
