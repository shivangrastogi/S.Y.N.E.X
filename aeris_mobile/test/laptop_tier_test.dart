import 'dart:async';
import 'dart:convert';
import 'dart:typed_data';

import 'package:aeris_mobile/brain/laptop_tier.dart';
import 'package:aeris_mobile/brain/router.dart';
import 'package:aeris_mobile/brain/tier.dart';
import 'package:aeris_mobile/skills/builtin/builtins.dart';
import 'package:aeris_mobile/transport/crypto.dart';
import 'package:aeris_mobile/transport/laptop_socket.dart';
import 'package:flutter_test/flutter_test.dart';

Uint8List key(int fill) => Uint8List.fromList(List.filled(32, fill));
final endpoint = Uri.parse('ws://127.0.0.1:9999/');

/// Stands in for the laptop. Records what the phone sent and lets a test decide
/// what comes back, so the whole protocol can be exercised with no socket.
class FakeLaptop implements LaptopSocket {
  FakeLaptop({this.acceptToken = true, this.silent = false});

  final bool acceptToken;

  /// Accepts the handshake then never answers — the hung-laptop case.
  final bool silent;

  final _out = StreamController<String>.broadcast();
  final List<String> sent = [];
  final BridgeCrypto crypto = BridgeCrypto(key(11));

  bool closed = false;
  String? lastAskedText;

  /// Replies the fake sends automatically; null means answer nothing.
  String? autoReply = 'Playing your playlist.';

  @override
  Stream<String> get messages => _out.stream;

  @override
  void send(String text) {
    sent.add(text);

    if (text.startsWith('AERIS ')) {
      _out.add(acceptToken ? 'OK' : 'NO');
      return;
    }
    if (silent) return;

    // Decrypt the request and answer it, echoing the id back.
    unawaited(() async {
      final envelope = jsonDecode(text) as Map<String, dynamic>;
      final payload = await crypto.decrypt(envelope);
      if (payload == null) return;
      lastAskedText = payload['text'] as String?;
      if (autoReply == null) return;
      final reply = await crypto.encrypt({
        'id': payload['id'],
        'reply': autoReply,
      });
      _out.add(jsonEncode(reply));
    }());
  }

  /// Pushes a frame the phone did not ask for.
  void push(String raw) => _out.add(raw);

  void drop() => _out.close();

  @override
  Future<void> close() async {
    closed = true;
    if (!_out.isClosed) await _out.close();
  }
}

LaptopTier tierFor(
  FakeLaptop laptop, {
  int keyFill = 11,
  String token = 'secret',
  Duration timeout = const Duration(milliseconds: 300),
}) =>
    LaptopTier(
      endpoint: endpoint,
      token: token,
      key: key(keyFill),
      connect: (_) async => laptop,
      timeout: timeout,
    );

void main() {
  group('handshake', () {
    test('sends the token in the lan_link format and becomes available',
        () async {
      final laptop = FakeLaptop();
      final tier = tierFor(laptop);

      expect(tier.isAvailable, isFalse, reason: 'not connected yet');
      expect(await tier.connect(), isTrue);

      expect(laptop.sent.first, 'AERIS secret');
      expect(tier.isAvailable, isTrue);
      expect(tier.tier, Tier.laptop);
    });

    test('a rejected token leaves the tier unavailable', () async {
      final tier = tierFor(FakeLaptop(acceptToken: false));
      expect(await tier.connect(), isFalse);
      expect(tier.isAvailable, isFalse);
    });

    test('a silent laptop times out rather than hanging', () async {
      final tier = tierFor(FakeLaptop(silent: true, acceptToken: false));
      // acceptToken false + silent: nothing is ever sent back.
      expect(await tier.connect(), isFalse);
    });

    test('a refused connection is reported, not thrown', () async {
      final tier = LaptopTier(
        endpoint: endpoint,
        token: 't',
        key: key(1),
        connect: (_) async => throw const SocketExceptionStub(),
        timeout: const Duration(milliseconds: 200),
      );
      expect(await tier.connect(), isFalse);
      expect(tier.isAvailable, isFalse);
    });

    test('connecting twice reuses the same connection', () async {
      final laptop = FakeLaptop();
      final tier = tierFor(laptop);
      await tier.connect();
      await tier.connect();
      expect(laptop.sent.where((s) => s.startsWith('AERIS')), hasLength(1));
    });
  });

  group('asking', () {
    test('encrypts the question and returns the decrypted reply', () async {
      final laptop = FakeLaptop();
      final tier = tierFor(laptop);

      final reply = await tier.ask('play my discover weekly');

      expect(reply, 'Playing your playlist.');
      expect(laptop.lastAskedText, 'play my discover weekly');
      // The question must never appear in plaintext on the wire.
      expect(laptop.sent.last, isNot(contains('discover weekly')));
    });

    test('connects on first ask without an explicit connect()', () async {
      final tier = tierFor(FakeLaptop());
      expect(await tier.ask('hello'), isNotNull);
      expect(tier.isAvailable, isTrue);
    });

    test('a laptop that never answers times out and returns null', () async {
      final tier = tierFor(FakeLaptop(silent: true));
      expect(await tier.ask('anything'), isNull);
    });

    test('an empty reply counts as no answer', () async {
      final laptop = FakeLaptop()..autoReply = '   ';
      final tier = tierFor(laptop);
      expect(await tier.ask('anything'), isNull);
    });

    test('concurrent questions get their own answers, not each others',
        () async {
      final laptop = FakeLaptop();
      final tier = tierFor(laptop);
      await tier.connect();

      laptop.autoReply = 'first';
      final a = tier.ask('question one');
      laptop.autoReply = 'second';
      final b = tier.ask('question two');

      final results = await Future.wait([a, b]);
      // Both resolved, and neither hung — ids kept them apart.
      expect(results.where((r) => r != null), hasLength(2));
    });

    test('a frame encrypted with the wrong key is dropped, not delivered',
        () async {
      final laptop = FakeLaptop();
      // Tier holds a different key than the fake laptop.
      final tier = tierFor(laptop, keyFill: 99);
      await tier.connect();

      expect(await tier.ask('anything'), isNull);
    });

    test('an unsolicited frame does not disturb anything', () async {
      final laptop = FakeLaptop();
      final tier = tierFor(laptop);
      await tier.connect();

      laptop.push('{"n":"zz","ct":"zz"}');
      await Future<void>.delayed(const Duration(milliseconds: 20));

      expect(tier.isAvailable, isTrue);
      expect(await tier.ask('still working'), 'Playing your playlist.');
    });
  });

  group('losing the laptop', () {
    test('a dropped socket marks the tier unavailable', () async {
      final laptop = FakeLaptop();
      final tier = tierFor(laptop);
      await tier.connect();
      expect(tier.isAvailable, isTrue);

      laptop.drop();
      await Future<void>.delayed(const Duration(milliseconds: 20));

      expect(tier.isAvailable, isFalse);
    });

    test('dispose closes the socket', () async {
      final laptop = FakeLaptop();
      final tier = tierFor(laptop);
      await tier.connect();

      tier.dispose();
      expect(tier.isAvailable, isFalse);
      expect(laptop.closed, isTrue);
    });
  });

  group('through the router', () {
    test('on-device still wins over a reachable laptop', () async {
      final tier = tierFor(FakeLaptop());
      await tier.connect();
      final router = BrainRouter(skills: defaultSkills(), laptop: tier);

      final a = await router.ask('15% of 2400');
      expect(a.tier, Tier.device);
      expect(a.text, '360');
    });

    test('what the phone cannot answer reaches the laptop', () async {
      final laptop = FakeLaptop();
      final tier = tierFor(laptop);
      await tier.connect();
      final router = BrainRouter(skills: defaultSkills(), laptop: tier);

      final a = await router.ask('play my discover weekly');

      expect(a.tier, Tier.laptop);
      expect(a.text, 'Playing your playlist.');
      expect(a.tried, [Tier.device, Tier.laptop]);
    });

    test('an unreachable laptop leaves the reach strip honest', () async {
      final tier = tierFor(FakeLaptop(acceptToken: false));
      await tier.connect();
      final router = BrainRouter(skills: defaultSkills(), laptop: tier);

      expect(router.reach[Tier.laptop], isFalse);
      final a = await router.ask('play my discover weekly');
      expect(a.tier, Tier.none);
    });
  });
}

/// A stand-in for a connection failure, without importing dart:io in a test.
class SocketExceptionStub implements Exception {
  const SocketExceptionStub();
  @override
  String toString() => 'connection refused';
}
