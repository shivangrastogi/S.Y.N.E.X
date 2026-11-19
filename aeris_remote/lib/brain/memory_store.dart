// Phone-local memory: "yaad rakho …" facts and quick notes, so remember /
// recall / forget / create_note work with no laptop and no internet.
// A JSON file in the app's private storage, never synced anywhere.
//
// Recall is keyword overlap with a light recency boost for now — the plan's
// Phase 5 (embeddings + sqlite-vec + FTS5) replaces the scorer, not the API.
import 'dart:convert';
import 'dart:io';

import 'package:path_provider/path_provider.dart';

class MemoryItem {
  final String text;
  final String kind; // fact | note
  final DateTime at;
  const MemoryItem(this.text, this.kind, this.at);

  Map<String, dynamic> toJson() => {'text': text, 'kind': kind, 'at': at.toIso8601String()};
  factory MemoryItem.fromJson(Map<String, dynamic> j) => MemoryItem(
      j['text'] as String, j['kind'] as String? ?? 'fact',
      DateTime.tryParse(j['at'] as String? ?? '') ?? DateTime.now());
}

class MemoryStore {
  MemoryStore({File? file}) : _fixedFile = file;
  static final MemoryStore instance = MemoryStore();

  final File? _fixedFile;
  List<MemoryItem>? _items;

  Future<File> _file() async =>
      _fixedFile ?? File('${(await getApplicationSupportDirectory()).path}/aeris_memory.json');

  Future<List<MemoryItem>> all() async {
    if (_items != null) return _items!;
    try {
      final f = await _file();
      if (await f.exists()) {
        _items = [
          for (final j in jsonDecode(await f.readAsString()) as List)
            MemoryItem.fromJson(j as Map<String, dynamic>)
        ];
      }
    } catch (_) {/* unreadable file → start empty, never crash a turn */}
    return _items ??= [];
  }

  Future<void> _save() async {
    final f = await _file();
    await f.writeAsString(jsonEncode([for (final m in _items!) m.toJson()]));
  }

  Future<void> add(String text, {String kind = 'fact'}) async {
    final items = await all();
    items.removeWhere((m) => m.kind == kind && _norm(m.text) == _norm(text));
    items.add(MemoryItem(text.trim(), kind, DateTime.now()));
    await _save();
  }

  /// Best matches for [query], most relevant first.
  Future<List<MemoryItem>> search(String query, {int limit = 3, String? kind}) async {
    final q = _words(query);
    final items = [for (final m in await all()) if (kind == null || m.kind == kind) m];
    if (q.isEmpty) return items.reversed.take(limit).toList();
    final scored = <(double, MemoryItem)>[];
    for (final (i, m) in items.indexed) {
      final w = _words(m.text);
      final hits = q.where(w.contains).length;
      if (hits == 0) continue;
      scored.add((hits / q.length + 0.05 * i / items.length, m));
    }
    scored.sort((a, b) => b.$1.compareTo(a.$1));
    return [for (final s in scored.take(limit)) s.$2];
  }

  /// Removes the items matching [query]; returns what was removed.
  Future<List<MemoryItem>> forget(String query) async {
    final hits = await search(query, limit: 1);
    if (hits.isEmpty) return const [];
    _items!.removeWhere(hits.contains);
    await _save();
    return hits;
  }

  /// Settings → Memory: delete one item / restore it (undo) / wipe all.
  Future<void> remove(MemoryItem m) async {
    (await all()).remove(m);
    await _save();
  }

  Future<void> restore(MemoryItem m, int index) async {
    final items = await all();
    items.insert(index.clamp(0, items.length), m);
    await _save();
  }

  Future<void> clear() async {
    (await all()).clear();
    await _save();
  }

  static String _norm(String s) => s.toLowerCase().replaceAll(RegExp(r'\s+'), ' ').trim();

  static const _stop = {
    'the', 'a', 'an', 'is', 'my', 'me', 'i', 'of', 'to', 'what', 'was', 'do',
    'you', 'about', 'ka', 'ki', 'ke', 'ko', 'hai', 'kya', 'mera', 'meri',
    'mere', 'tha', 'thi', 'kaun', 'kahan', 'remember', 'yaad', 'that',
  };

  static Set<String> _words(String s) => {
        for (final w in s.toLowerCase().split(RegExp(r'[^a-z0-9ऀ-ॿ]+')))
          if (w.length > 1 && !_stop.contains(w)) w
      };
}
