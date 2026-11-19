// AES-256-GCM — byte-for-byte compatible with core/cloud_bridge.py.
//
// Python side: 12-byte nonce, AES-GCM, message = {"n": b64(nonce),
// "ct": b64(ciphertext||tag)}. The `cryptography` package appends the
// 16-byte tag to the ciphertext, exactly like Python's AESGCM.
import 'dart:convert';
import 'package:cryptography/cryptography.dart';

class BridgeCrypto {
  final SecretKey _key;
  final AesGcm _algo = AesGcm.with256bits();

  BridgeCrypto(List<int> keyBytes) : _key = SecretKey(keyBytes);

  /// payload map -> {"n":..,"ct":..} ready for Firestore.
  Future<Map<String, String>> encrypt(Map<String, dynamic> payload) async {
    final nonce = _algo.newNonce(); // 12 bytes
    final plain = utf8.encode(jsonEncode(payload));
    final box = await _algo.encrypt(plain, secretKey: _key, nonce: nonce);
    // Match Python: ciphertext followed by the auth tag.
    final ctPlusTag = <int>[...box.cipherText, ...box.mac.bytes];
    return {
      'n': base64.encode(nonce),
      'ct': base64.encode(ctPlusTag),
    };
  }

  /// {"n":..,"ct":..} -> payload map, or null on tamper/wrong key.
  Future<Map<String, dynamic>?> decrypt(Map<String, dynamic> doc) async {
    try {
      final nonce = base64.decode(doc['n'] as String);
      final all = base64.decode(doc['ct'] as String);
      if (all.length < 16) return null;
      final ct = all.sublist(0, all.length - 16);
      final tag = all.sublist(all.length - 16);
      final box = SecretBox(ct, nonce: nonce, mac: Mac(tag));
      final plain = await _algo.decrypt(box, secretKey: _key);
      return jsonDecode(utf8.decode(plain)) as Map<String, dynamic>;
    } catch (_) {
      return null; // bad key or corrupted — silently drop
    }
  }
}
