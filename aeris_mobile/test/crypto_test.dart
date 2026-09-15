import 'dart:convert';
import 'dart:typed_data';

import 'package:aeris_mobile/transport/crypto.dart';
import 'package:flutter_test/flutter_test.dart';

Uint8List key(int fill) => Uint8List.fromList(List.filled(32, fill));

void main() {
  group('BridgeCrypto', () {
    test('round-trips a payload', () async {
      final c = BridgeCrypto(key(7));
      final envelope = await c.encrypt({'cmd': 'ask', 'text': 'kya haal hai'});

      expect(envelope.keys, containsAll(['n', 'ct']));
      final out = await c.decrypt(envelope);

      expect(out, isNotNull);
      expect(out!['cmd'], 'ask');
      expect(out['text'], 'kya haal hai');
    });

    test('uses a fresh 12-byte nonce every time', () async {
      final c = BridgeCrypto(key(3));
      final a = await c.encrypt({'v': 1});
      final b = await c.encrypt({'v': 1});

      expect(base64.decode(a['n']!).length, BridgeCrypto.nonceLength);
      expect(a['n'], isNot(b['n']), reason: 'nonce reuse breaks AES-GCM');
      expect(a['ct'], isNot(b['ct']));
    });

    test('appends the 16-byte tag to the ciphertext, as Python does', () async {
      final c = BridgeCrypto(key(9));
      final envelope = await c.encrypt({'a': 'bc'});
      final plainLength = utf8.encode(jsonEncode({'a': 'bc'})).length;

      expect(
        base64.decode(envelope['ct']!).length,
        plainLength + BridgeCrypto.tagLength,
      );
    });

    test('returns null for the wrong key rather than throwing', () async {
      final envelope = await BridgeCrypto(key(1)).encrypt({'secret': 'x'});
      expect(await BridgeCrypto(key(2)).decrypt(envelope), isNull);
    });

    test('returns null when the ciphertext is tampered with', () async {
      final c = BridgeCrypto(key(5));
      final envelope = await c.encrypt({'amount': 100});

      final bytes = base64.decode(envelope['ct']!);
      bytes[0] ^= 0xFF;
      final tampered = {'n': envelope['n']!, 'ct': base64.encode(bytes)};

      expect(await c.decrypt(tampered), isNull);
    });

    test('returns null on malformed envelopes', () async {
      final c = BridgeCrypto(key(4));
      expect(await c.decrypt({}), isNull);
      expect(await c.decrypt({'n': 123, 'ct': 'zz'}), isNull);
      expect(await c.decrypt({'n': base64.encode([1, 2]), 'ct': 'AAAA'}), isNull);
      expect(await c.decrypt({'n': 'not base64!!', 'ct': 'AAAA'}), isNull);
    });

    test('rejects a key that is not 32 bytes', () {
      expect(() => BridgeCrypto(List.filled(16, 0)), throwsA(isA<AssertionError>()));
    });
  });
}
