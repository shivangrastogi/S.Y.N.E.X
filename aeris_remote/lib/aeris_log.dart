// A9 — a tiny in-app error/event log so failures stop being invisible.
// Many code paths swallow errors with `catch (_) {}`; routing the ones that
// matter here makes them visible in-app (Assistant → Logs) instead of lost.
import 'package:flutter/foundation.dart';

class AerisLog {
  AerisLog._();

  /// Newest-last list of "HH:MM:SS  tag: message" lines, capped.
  static final ValueNotifier<List<String>> lines =
      ValueNotifier<List<String>>(<String>[]);
  static const _cap = 200;

  static void add(String tag, Object message) {
    final now = DateTime.now();
    String two(int n) => n.toString().padLeft(2, '0');
    final stamp = '${two(now.hour)}:${two(now.minute)}:${two(now.second)}';
    final line = '$stamp  $tag: $message';
    final next = List<String>.from(lines.value)..add(line);
    if (next.length > _cap) next.removeRange(0, next.length - _cap);
    lines.value = next;
    if (kDebugMode) debugPrint('[AERIS] $line');
  }

  static void clear() => lines.value = <String>[];
}
