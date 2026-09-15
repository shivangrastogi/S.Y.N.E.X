// Phone-side file transfer (Phase 6) — mirrors core/cloud_bridge.py's
// chunked `file_chunk` protocol (tid/name/index/total/size/data, base64).
//
//   onChunk()     — reassemble an incoming file (laptop → phone), save it.
//   pickAndSend() — pick a file and stream it to the laptop (phone → laptop).
import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';
import 'package:file_picker/file_picker.dart';
import 'package:path_provider/path_provider.dart';
import 'bridge_client.dart';

class _Rx {
  final int total;
  final String name;
  final Map<int, Uint8List> chunks = {};
  _Rx(this.total, this.name);
}

class PhoneFileTransfer {
  static const _chunk = 400000; // matches the laptop's chunk size
  final Map<String, _Rx> _rx = {};

  /// Feed an incoming `file_chunk`. Returns the saved path once the file is
  /// complete, else null.
  Future<String?> onChunk(Map<String, dynamic> e) async {
    final tid = e['tid'] as String?;
    if (tid == null) return null;
    final total = (e['total'] as num?)?.toInt() ?? 1;
    final name = (e['name'] ?? 'aeris_file').toString();
    final idx = (e['index'] as num?)?.toInt() ?? 0;
    final r = _rx.putIfAbsent(tid, () => _Rx(total, name));
    try {
      r.chunks[idx] = base64Decode(e['data'] as String);
    } catch (_) {
      return null;
    }
    if (r.chunks.length < r.total) return null;
    _rx.remove(tid);
    final buf = BytesBuilder();
    for (var i = 0; i < r.total; i++) {
      final c = r.chunks[i];
      if (c == null) return null; // missing chunk — give up
      buf.add(c);
    }
    try {
      final dir = (await getExternalStorageDirectory()) ??
          (await getApplicationDocumentsDirectory());
      final f = File('${dir.path}/${r.name}');
      await f.writeAsBytes(buf.toBytes());
      return f.path;
    } catch (_) {
      return null;
    }
  }

  /// Pick a file and stream it to the laptop over the relay. Returns the
  /// file name on success, else null.
  Future<String?> pickAndSend(BridgeClient bridge) async {
    final res = await FilePicker.platform.pickFiles(withData: false);
    if (res == null || res.files.isEmpty) return null;
    final pf = res.files.first;
    final path = pf.path;
    if (path == null) return null;
    final bytes = await File(path).readAsBytes();
    final name = pf.name;
    final total = ((bytes.length + _chunk - 1) ~/ _chunk).clamp(1, 100000);
    final tid = DateTime.now().microsecondsSinceEpoch.toRadixString(16);
    for (var i = 0; i < total; i++) {
      final end = ((i + 1) * _chunk).clamp(0, bytes.length);
      final piece = bytes.sublist(i * _chunk, end);
      await bridge.send(name, type: 'file_chunk', extra: {
        'tid': tid,
        'name': name,
        'index': i,
        'total': total,
        'size': bytes.length,
        'data': base64Encode(piece),
      });
    }
    return name;
  }
}
