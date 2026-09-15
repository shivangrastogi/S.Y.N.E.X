// Pairing store — holds the pid + AES key received from the laptop's QR.
//
// The QR (rendered by core/cloud_bridge.new_pairing) carries:
//   {"v":1,"kind":"aeris-bridge","project":..,"pid":<hex>,"key":<b64>}
// We keep pid + key in secure storage; the key never leaves the device.
import 'dart:convert';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

class Pairing {
  final String pid;
  final String keyB64;
  final String project;

  Pairing({required this.pid, required this.keyB64, required this.project});

  List<int> get keyBytes => base64.decode(keyB64);

  /// Parse a scanned QR string. Returns null if it isn't an AERIS pairing.
  static Pairing? fromQr(String raw) {
    try {
      final j = jsonDecode(raw) as Map<String, dynamic>;
      if (j['kind'] != 'aeris-bridge') return null;
      if (j['pid'] == null || j['key'] == null) return null;
      return Pairing(
        pid: j['pid'] as String,
        keyB64: j['key'] as String,
        project: (j['project'] ?? '') as String,
      );
    } catch (_) {
      return null;
    }
  }
}

class PairingStore {
  static const _k = 'aeris_pairing';
  final _storage = const FlutterSecureStorage();

  Future<void> save(Pairing p) => _storage.write(
        key: _k,
        value: jsonEncode({'pid': p.pid, 'key': p.keyB64, 'project': p.project}),
      );

  Future<Pairing?> load() async {
    final s = await _storage.read(key: _k);
    if (s == null) return null;
    final j = jsonDecode(s) as Map<String, dynamic>;
    return Pairing(
      pid: j['pid'] as String,
      keyB64: j['key'] as String,
      project: (j['project'] ?? '') as String,
    );
  }

  Future<void> clear() => _storage.delete(key: _k);
}
