import 'dart:convert';

import 'package:cryptography/cryptography.dart';

/// How the phone and the laptop agree on a key without either sending it.
///
/// The user types the same passphrase in both places and each side derives the
/// same 32 bytes. No key ever crosses the network, and nothing is stored that
/// an attacker could replay — which is why this is a KDF and not "hash the
/// password", and why the iteration count is deliberately expensive.
///
/// The laptop must use the identical parameters or every frame will simply
/// fail to decrypt:
///
/// ```python
/// # core/phone_server.py
/// key = hashlib.pbkdf2_hmac(
///     "sha256", passphrase.encode(), b"aeris-pairing-v1", 120_000, dklen=32)
/// ```
class LaptopPairing {
  const LaptopPairing({
    required this.host,
    this.port = defaultPort,
    required this.passphrase,
  });

  /// Chosen to sit clear of the laptop's existing servers — `health_server`
  /// and `lan_link` both already hold ports.
  static const int defaultPort = 8770;

  /// Fixed and shared with the laptop. A per-user salt would be better, but it
  /// would have to be exchanged, and the whole point is that nothing is.
  static const String salt = 'aeris-pairing-v1';

  /// Expensive on purpose: a short passphrase should still cost an attacker
  /// real time per guess.
  static const int iterations = 120000;

  final String host;
  final int port;
  final String passphrase;

  static const LaptopPairing none =
      LaptopPairing(host: '', passphrase: '');

  bool get isConfigured => problem == null;

  Uri get endpoint => Uri.parse('ws://$host:$port/');

  /// A short passphrase is the weak link in the whole scheme, so it is refused
  /// rather than warned about.
  static const int minPassphrase = 8;

  /// Human-readable reason this pairing cannot be used, or null when it can.
  String? get problem {
    if (host.trim().isEmpty) return 'Enter the laptop\'s address.';
    if (!_looksLikeHost(host.trim())) {
      return 'That does not look like an address. Try something like 192.168.1.5.';
    }
    if (port < 1 || port > 65535) return 'Port must be between 1 and 65535.';
    if (passphrase.length < minPassphrase) {
      return 'Use at least $minPassphrase characters, the same on both devices.';
    }
    return null;
  }

  LaptopPairing copyWith({String? host, int? port, String? passphrase}) =>
      LaptopPairing(
        host: host ?? this.host,
        port: port ?? this.port,
        passphrase: passphrase ?? this.passphrase,
      );

  /// Derives the AES-256 key. Slow by design — call it once at connect time,
  /// never per message.
  Future<List<int>> deriveKey() => deriveKeyFrom(passphrase);

  static Future<List<int>> deriveKeyFrom(String passphrase) async {
    final pbkdf2 = Pbkdf2(
      macAlgorithm: Hmac.sha256(),
      iterations: iterations,
      bits: 256,
    );
    final key = await pbkdf2.deriveKey(
      secretKey: SecretKey(utf8.encode(passphrase)),
      nonce: utf8.encode(salt),
    );
    return key.extractBytes();
  }

  static bool _looksLikeHost(String h) {
    // An IPv4 address, or a hostname like "shivang-laptop.local".
    if (RegExp(r'^\d{1,3}(\.\d{1,3}){3}$').hasMatch(h)) {
      return h.split('.').every((p) => int.parse(p) <= 255);
    }
    return RegExp(r'^[a-zA-Z0-9]([a-zA-Z0-9\-.]*[a-zA-Z0-9])?$').hasMatch(h);
  }

  @override
  bool operator ==(Object other) =>
      other is LaptopPairing &&
      other.host == host &&
      other.port == port &&
      other.passphrase == passphrase;

  @override
  int get hashCode => Object.hash(host, port, passphrase);

  /// Never includes the passphrase — this ends up in logs.
  @override
  String toString() => 'LaptopPairing($host:$port)';
}
