import 'dart:io';

import 'package:path_provider/path_provider.dart';

/// Persistent cache of synthesised speech chunks, so a phrase AERIS has said
/// once plays instantly forever after. Same idea as the desktop's
/// core/tts_cache.py. Measured reason (RMX3741 self-test, 2026-11-17): every
/// fresh synthesis pays ~2 s fixed start-up, even for a 1.4 s phrase.
///
/// Files are `<key>_<ms>.wav`: the key hashes everything that changes the
/// audio (text, speed, language, voice), the suffix stores its length.
class VoiceCache {
  VoiceCache._(this.dir);
  final Directory dir;
  final _index = <String, (String, int)>{}; // key → (path, ms)

  static const maxFiles = 400;
  static VoiceCache? _instance;

  static Future<VoiceCache> open() async {
    if (_instance != null) return _instance!;
    final base = await getApplicationSupportDirectory();
    final dir = Directory('${base.path}/voice_cache_v1');
    await dir.create(recursive: true);
    final c = VoiceCache._(dir);
    await for (final f in dir.list()) {
      final m = RegExp(r'([0-9a-f]{16})_(\d+)\.wav$').firstMatch(f.path);
      if (m != null) c._index[m[1]!] = (f.path, int.parse(m[2]!));
    }
    return _instance = c;
  }

  /// FNV-1a 64-bit — stable, dependency-free, plenty for a cache key.
  static String keyOf(String spoken, double speed, String lang, int sid) {
    var h = 0xcbf29ce484222325;
    for (final b in '$sid|$lang|${speed.toStringAsFixed(3)}|$spoken'.codeUnits) {
      h ^= b;
      h *= 0x100000001b3; // wraps mod 2^64 on the VM, as FNV wants
    }
    // Dart ints are signed: print the two 32-bit halves unsigned, so a key is
    // always exactly 16 hex digits (a "-" broke the file-name index).
    String half(int v) => (v & 0xFFFFFFFF).toRadixString(16).padLeft(8, '0');
    return '${half(h >>> 32)}${half(h)}';
  }

  (String, int)? get(String key) {
    final hit = _index[key];
    if (hit == null) return null;
    if (!File(hit.$1).existsSync()) {
      _index.remove(key);
      return null;
    }
    try {
      File(hit.$1).setLastModifiedSync(DateTime.now()); // LRU
    } catch (_) {}
    return hit;
  }

  String tempPath(String key) => '${dir.path}/$key.tmp.wav';

  /// Move a freshly written temp file into the cache.
  Future<(String, int)> put(String key, int ms) async {
    final path = '${dir.path}/${key}_$ms.wav';
    await File(tempPath(key)).rename(path);
    _index[key] = (path, ms);
    if (_index.length > maxFiles) await _prune();
    return (path, ms);
  }

  Future<void> _prune() async {
    final files = [
      for (final e in _index.entries)
        if (File(e.value.$1).existsSync()) (e.key, File(e.value.$1).lastModifiedSync()),
    ]..sort((a, b) => a.$2.compareTo(b.$2));
    for (final (key, _) in files.take(files.length - maxFiles * 3 ~/ 4)) {
      try {
        await File(_index[key]!.$1).delete();
      } catch (_) {}
      _index.remove(key);
    }
  }

  int get size => _index.length;
}
