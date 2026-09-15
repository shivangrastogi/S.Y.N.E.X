/// AES-256-GCM, byte-for-byte compatible with `core/cloud_bridge.py` on the
/// laptop and with `aeris_remote/lib/crypto.dart`.
///
/// Wire format: `{"n": base64(12-byte nonce), "ct": base64(ciphertext || tag)}`.
/// Python's `AESGCM` appends the 16-byte tag to the ciphertext; the Dart
/// `cryptography` package keeps the MAC separate, so this splits and rejoins it.
/// Keeping the format identical means the laptop cannot tell which phone app
/// is talking to it, and a pairing works for both.
library;

import 'dart:convert';

import 'package:cryptography/cryptography.dart';

class BridgeCrypto {
  BridgeCrypto(List<int> keyBytes)
      : assert(keyBytes.length == 32, 'AES-256 needs a 32-byte key'),
        _key = SecretKey(keyBytes);

  static const int nonceLength = 12;
  static const int tagLength = 16;

  final SecretKey _key;
  final AesGcm _algo = AesGcm.with256bits();

  /// Encrypts [payload] into the `{n, ct}` envelope the laptop expects.
  Future<Map<String, String>> encrypt(Map<String, dynamic> payload) async {
    final nonce = _algo.newNonce();
    final plain = utf8.encode(jsonEncode(payload));
    final box = await _algo.encrypt(plain, secretKey: _key, nonce: nonce);
    return {
      'n': base64.encode(nonce),
      'ct': base64.encode(<int>[...box.cipherText, ...box.mac.bytes]),
    };
  }

  /// Decrypts an envelope, or returns null when the key is wrong, the payload
  /// was tampered with, or the fields are malformed.
  ///
  /// Null rather than an exception on purpose: a bad envelope on a shared relay
  /// is an expected event, not a crash, and the caller should drop it quietly.
  Future<Map<String, dynamic>?> decrypt(Map<String, dynamic> envelope) async {
    try {
      final n = envelope['n'];
      final ct = envelope['ct'];
      if (n is! String || ct is! String) return null;

      final nonce = base64.decode(n);
      if (nonce.length != nonceLength) return null;

      final all = base64.decode(ct);
      if (all.length < tagLength) return null;

      final cipherText = all.sublist(0, all.length - tagLength);
      final mac = all.sublist(all.length - tagLength);

      final plain = await _algo.decrypt(
        SecretBox(cipherText, nonce: nonce, mac: Mac(mac)),
        secretKey: _key,
      );
      final decoded = jsonDecode(utf8.decode(plain));
      return decoded is Map<String, dynamic> ? decoded : null;
    } catch (_) {
      return null;
    }
  }
}
