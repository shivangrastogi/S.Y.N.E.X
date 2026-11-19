// "Which remembered facts match this sentence?" — shared by the rule router
// (recall), the brain bridge (recall tool) and the brain's prompt (the facts it
// is shown each turn). Word overlap after dropping filler words; tiny lists,
// so no index is needed.
import '../core/models.dart';
import 'parse.dart';

/// Remembered facts that share at least one meaningful word with [sentence],
/// best match first, at most [limit].
List<Memory> matchingMemories(String sentence, List<Memory> memories, {int limit = 3}) {
  final sentenceWords = keywords(sentence);
  final scored = <(Memory, int)>[];
  for (final memory in memories) {
    final overlap = keywords(memory.text).intersection(sentenceWords).length;
    if (overlap > 0) scored.add((memory, overlap));
  }
  scored.sort((a, b) => b.$2.compareTo(a.$2)); // most shared words first
  return [for (final (memory, _) in scored.take(limit)) memory];
}

/// The single best match for [sentence], or null if nothing overlaps.
Memory? bestMatchingMemory(String sentence, List<Memory> memories) =>
    matchingMemories(sentence, memories, limit: 1).firstOrNull;

/// The facts shown to the brain each turn: word matches first, then the most
/// recent ones, up to [limit]. Word overlap misses synonyms ("gaadi" vs
/// "car") but the brain doesn't, so it gets recent facts as well.
List<Memory> memoriesForPrompt(String sentence, List<Memory> memories, {int limit = 5}) {
  final chosen = matchingMemories(sentence, memories, limit: limit);
  for (final memory in memories) {
    // the store keeps the newest first
    if (chosen.length >= limit) break;
    if (!chosen.contains(memory)) chosen.add(memory);
  }
  return chosen;
}
