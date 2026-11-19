// System prompt + chat rendering — a byte-identical port of
// aeris_brain/brain/prompt.py and the Qwen3 chat template the model is
// trained with (enable_thinking=False). Any drift here costs accuracy
// silently, so test/brain_contract_test.dart compares against golden text
// written by `py -3.10 -m scripts.sync_app` (in aeris_brain/).
import 'contract.dart';

const persona =
    "You are AERIS, a voice assistant living on the user's Android phone. "
    'You understand English, Hindi written in English letters (Hinglish), and any mix.';

const contractText = '''Answer with exactly ONE JSON object, nothing else:
- {"type":"tool_call","calls":[{"name":TOOL,"args":{...}}]} to act. Use only the tools listed. Several calls are allowed if the user asked for several things.
- {"type":"ask","text":QUESTION,"pending":TOOL} when a required detail is missing. Never guess names, numbers, times or message text.
- {"type":"reply","text":TEXT} for small talk and simple answers you are sure of.
- {"type":"plan","goal":GOAL,"steps":[STEP,...]} when the task needs operating other apps step by step (e.g. make an image in Gemini, then send it on WhatsApp).
- {"type":"escalate","reason":"knowledge"|"live_info"|"complex"|"no_tool","query":TEXT} for facts you may not know, live information (weather, news, scores, prices), long reasoning, or requests no tool can do.
Rules: copy names, numbers, times, places and message text exactly as the user said them. Set optional args only when the user said them. Replies are spoken aloud: 1-2 short sentences, no lists, no markdown.''';

const langRules = {
  'english': 'Language: reply in simple English only, never Hindi words.',
  'hinglish': 'Language: reply in natural Hinglish (Hindi in English letters, mixed with English).',
  'match': 'Language: reply in the same language style the user used.',
};

/// One-line signature: required params first, then optional (`?`).
String signature(ToolSpec tool) {
  final req = tool.required;
  final order = [...req, ...tool.params.keys.where((p) => !req.contains(p))];
  final parts = <String>[];
  for (final name in order) {
    final p = tool.params[name]!;
    final typ = switch (p.type) {
      'enum' => p.values.join('|'),
      'integer' => 'int',
      'boolean' => 'bool',
      'number' => 'number',
      'any' => p.hint ?? 'any',
      _ => 'str',
    };
    parts.add('$name${req.contains(name) ? '' : '?'}: $typ');
  }
  var sig = '${tool.name}(${parts.join(', ')})';
  if (tool.oneOf.isNotEmpty) sig += '  [one of: ${tool.oneOf.join(', ')}]';
  return '$sig — ${tool.description}';
}

/// The fixed part: identical every turn, so its KV cache is computed once.
String basePrompt(List<ToolSpec> tools, {String lang = 'match'}) => [
      persona,
      langRules[lang]!,
      'Tools:\n${tools.map((t) => '- ${signature(t)}').join('\n')}',
      contractText,
    ].join('\n\n');

/// [lang]: 'english' | 'hinglish' | 'match'. [now] and [memory] change from
/// turn to turn and come LAST (after the contract), so everything before them
/// stays a reusable prefix.
String systemPrompt(List<ToolSpec> tools, {String lang = 'match', String? now, List<String>? memory}) {
  final lines = [basePrompt(tools, lang: lang)];
  if (now != null) lines.add('Now: $now.');
  if (memory != null && memory.isNotEmpty) {
    lines.add('Things the user told you to remember:\n${memory.map((m) => '- $m').join('\n')}');
  }
  return lines.join('\n\n');
}

/// A past turn: role 'user' or 'assistant' (assistant = canonical JSON).
typedef Turn = ({String role, String content});

const imStart = '<|im_start|>';
const imEnd = '<|im_end|>';

/// The Qwen3 ChatML prompt the model continues, ending with the empty
/// think block that `enable_thinking=False` adds.
String qwenPrompt(String system, List<Turn> turns) {
  final b = StringBuffer('${imStart}system\n$system$imEnd\n');
  for (final t in turns) {
    b.write('$imStart${t.role}\n${t.content}$imEnd\n');
  }
  b.write('${imStart}assistant\n<think>\n\n</think>\n\n');
  return b.toString();
}

/// The text every prompt starts with — what [BrainRuntime.warmPrefix] caches.
String cachedPrefix(String base) => '${imStart}system\n$base';
