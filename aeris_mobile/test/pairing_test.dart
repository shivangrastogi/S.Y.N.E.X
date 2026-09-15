import 'dart:convert';

import 'package:aeris_mobile/transport/crypto.dart';
import 'package:aeris_mobile/transport/pairing.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  group('validation', () {
    test('accepts a sensible pairing', () {
      const p = LaptopPairing(host: '192.168.1.5', passphrase: 'correct-horse');
      expect(p.problem, isNull);
      expect(p.isConfigured, isTrue);
    });

    test('accepts an mDNS hostname', () {
      const p =
          LaptopPairing(host: 'shivang-laptop.local', passphrase: 'correct-horse');
      expect(p.problem, isNull);
    });

    test('asks for an address when empty', () {
      expect(const LaptopPairing(host: '', passphrase: 'correct-horse').problem,
          contains('address'));
    });

    test('rejects nonsense addresses with an example', () {
      final problem =
          const LaptopPairing(host: 'not a host!', passphrase: 'correct-horse')
              .problem;
      expect(problem, contains('192.168.1.5'));
    });

    test('rejects an out-of-range IPv4 octet', () {
      expect(
        const LaptopPairing(host: '192.168.1.999', passphrase: 'correct-horse')
            .problem,
        isNotNull,
      );
    });

    test('rejects an impossible port', () {
      expect(
        const LaptopPairing(host: '10.0.0.2', port: 0, passphrase: 'correct-horse')
            .problem,
        contains('Port'),
      );
      expect(
        const LaptopPairing(
                host: '10.0.0.2', port: 70000, passphrase: 'correct-horse')
            .problem,
        contains('Port'),
      );
    });

    test('refuses a short passphrase rather than warning about it', () {
      final problem =
          const LaptopPairing(host: '10.0.0.2', passphrase: 'short').problem;
      expect(problem, contains('${LaptopPairing.minPassphrase} characters'));
      expect(problem, contains('both devices'));
    });

    test('the unconfigured default is not usable', () {
      expect(LaptopPairing.none.isConfigured, isFalse);
    });
  });

  group('endpoint', () {
    test('builds a ws url with the default port', () {
      const p = LaptopPairing(host: '192.168.1.5', passphrase: 'correct-horse');
      expect(p.endpoint.toString(), 'ws://192.168.1.5:8770/');
    });

    test('honours a custom port', () {
      const p = LaptopPairing(
          host: '192.168.1.5', port: 9001, passphrase: 'correct-horse');
      expect(p.endpoint.toString(), 'ws://192.168.1.5:9001/');
    });
  });

  group('key derivation', () {
    test('produces 32 bytes for AES-256', () async {
      final key = await LaptopPairing.deriveKeyFrom('correct-horse-battery');
      expect(key, hasLength(32));
    });

    test('is deterministic, so both devices land on the same key', () async {
      final a = await LaptopPairing.deriveKeyFrom('correct-horse-battery');
      final b = await LaptopPairing.deriveKeyFrom('correct-horse-battery');
      expect(a, b);
    });

    test('a different passphrase gives a different key', () async {
      final a = await LaptopPairing.deriveKeyFrom('correct-horse-battery');
      final b = await LaptopPairing.deriveKeyFrom('correct-horse-batterz');
      expect(a, isNot(b));
    });

    test('derived keys actually work with the bridge envelope', () async {
      final key = await LaptopPairing.deriveKeyFrom('correct-horse-battery');
      final crypto = BridgeCrypto(key);

      final envelope = await crypto.encrypt({'cmd': 'ask', 'text': 'namaste'});
      final back = await crypto.decrypt(envelope);

      expect(back!['text'], 'namaste');
    });

    test('two devices that typed different passphrases cannot talk', () async {
      final mine = BridgeCrypto(
          await LaptopPairing.deriveKeyFrom('correct-horse-battery'));
      final theirs =
          BridgeCrypto(await LaptopPairing.deriveKeyFrom('something-else-x'));

      final envelope = await mine.encrypt({'secret': 'x'});
      expect(await theirs.decrypt(envelope), isNull);
    });

    test('the salt and iteration count are pinned', () {
      // If either changes, every existing pairing silently breaks — so the
      // values are asserted here to make that a deliberate, visible decision.
      expect(LaptopPairing.salt, 'aeris-pairing-v1');
      expect(LaptopPairing.iterations, 120000);
      expect(utf8.encode(LaptopPairing.salt), hasLength(16));
    });
  });

  group('hygiene', () {
    test('toString never leaks the passphrase', () {
      const p =
          LaptopPairing(host: '10.0.0.2', passphrase: 'super-secret-value');
      expect(p.toString(), isNot(contains('super-secret')));
      expect(p.toString(), contains('10.0.0.2'));
    });

    test('copyWith replaces one field at a time', () {
      const p = LaptopPairing(host: '10.0.0.2', passphrase: 'correct-horse');
      expect(p.copyWith(port: 9001).host, '10.0.0.2');
      expect(p.copyWith(host: '10.0.0.3').passphrase, 'correct-horse');
    });

    test('equality compares every field', () {
      const a = LaptopPairing(host: 'h', passphrase: 'correct-horse');
      expect(a, const LaptopPairing(host: 'h', passphrase: 'correct-horse'));
      expect(a, isNot(const LaptopPairing(host: 'h', passphrase: 'other-phrase')));
    });
  });
}
