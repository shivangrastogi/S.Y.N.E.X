import 'package:aeris_mobile/brain/laptop_tier.dart';
import 'package:aeris_mobile/brain/router.dart';
import 'package:aeris_mobile/brain/tier.dart';
import 'package:aeris_mobile/skills/builtin/builtins.dart';
import 'package:aeris_mobile/state/laptop_connection.dart';
import 'package:aeris_mobile/store/settings_store.dart';
import 'package:aeris_mobile/transport/pairing.dart';
import 'package:flutter_test/flutter_test.dart';

import 'laptop_tier_test.dart' show FakeLaptop;

const good = LaptopPairing(host: '192.168.1.5', passphrase: 'correct-horse');

/// Builds a connection whose tier talks to [laptop] instead of a real socket.
({LaptopConnection link, BrainRouter router, MemorySettingsStore store})
    harness(FakeLaptop laptop) {
  final router = BrainRouter(skills: defaultSkills());
  final store = MemorySettingsStore();
  final link = LaptopConnection(
    router: router,
    store: store,
    build: (pairing, key) => LaptopTier(
      endpoint: pairing.endpoint,
      token: pairing.passphrase,
      key: key,
      connect: (_) async => laptop,
      timeout: const Duration(milliseconds: 400),
    ),
  );
  return (link: link, router: router, store: store);
}

void main() {
  group('connecting', () {
    test('starts unpaired', () {
      final h = harness(FakeLaptop());
      expect(h.link.state, LinkState.unpaired);
      expect(h.router.reach[Tier.laptop], isFalse);
    });

    test('a good pairing connects, saves, and lights the tier', () async {
      final h = harness(FakeLaptop());

      expect(await h.link.connect(good), isTrue);

      expect(h.link.state, LinkState.connected);
      expect(h.link.problem, isNull);
      expect(h.router.reach[Tier.laptop], isTrue);
      expect((await h.store.loadPairing()).host, '192.168.1.5');
    });

    test('an invalid pairing fails without touching the network', () async {
      final laptop = FakeLaptop();
      final h = harness(laptop);

      final ok = await h.link.connect(
        const LaptopPairing(host: '192.168.1.5', passphrase: 'short'),
      );

      expect(ok, isFalse);
      expect(h.link.state, LinkState.failed);
      expect(h.link.problem, contains('characters'));
      expect(laptop.sent, isEmpty, reason: 'never opened a socket');
    });

    test('a rejected token gives advice, not a stack trace', () async {
      final h = harness(FakeLaptop(acceptToken: false));

      expect(await h.link.connect(good), isFalse);
      expect(h.link.state, LinkState.failed);
      expect(h.link.problem, contains('same Wi-Fi'));
      expect(h.router.reach[Tier.laptop], isFalse);
    });

    test('a failed pairing is not saved', () async {
      final h = harness(FakeLaptop(acceptToken: false));
      await h.link.connect(good);
      expect((await h.store.loadPairing()).isConfigured, isFalse);
    });

    test('notifies on every state change', () async {
      final h = harness(FakeLaptop());
      var notified = 0;
      h.link.addListener(() => notified++);

      await h.link.connect(good);

      // connecting, then connected.
      expect(notified, greaterThanOrEqualTo(2));
    });
  });

  group('restoring', () {
    test('reconnects a saved pairing on boot', () async {
      final h = harness(FakeLaptop());
      await h.store.savePairing(good);

      await h.link.restore();

      expect(h.link.state, LinkState.connected);
      expect(h.router.reach[Tier.laptop], isTrue);
    });

    test('does nothing when nothing was paired', () async {
      final h = harness(FakeLaptop());
      await h.link.restore();
      expect(h.link.state, LinkState.unpaired);
    });

    test('a saved pairing that will not connect leaves it failed, not lost',
        () async {
      final h = harness(FakeLaptop(acceptToken: false));
      await h.store.savePairing(good);

      await h.link.restore();

      expect(h.link.state, LinkState.failed);
      // The pairing survives, so retry() has something to work with.
      expect(h.link.pairing.host, '192.168.1.5');
      expect((await h.store.loadPairing()).isConfigured, isTrue);
    });
  });

  group('retry and forget', () {
    test('retry reuses the saved pairing', () async {
      final h = harness(FakeLaptop());
      await h.store.savePairing(good);
      await h.link.restore();

      expect(await h.link.retry(), isTrue);
      expect(h.link.state, LinkState.connected);
    });

    test('retry does nothing when unpaired', () async {
      final h = harness(FakeLaptop());
      expect(await h.link.retry(), isFalse);
    });

    test('forget clears storage and detaches the tier', () async {
      final h = harness(FakeLaptop());
      await h.link.connect(good);
      expect(h.router.reach[Tier.laptop], isTrue);

      await h.link.forget();

      expect(h.link.state, LinkState.unpaired);
      expect(h.router.reach[Tier.laptop], isFalse);
      expect((await h.store.loadPairing()).isConfigured, isFalse);
    });

    test('reconnecting replaces the old tier rather than stacking one',
        () async {
      final first = FakeLaptop();
      final h = harness(first);
      await h.link.connect(good);
      await h.link.connect(good.copyWith(host: '192.168.1.6'));

      expect(first.closed, isTrue, reason: 'the old socket must be closed');
      expect(h.link.state, LinkState.connected);
    });
  });

  group('end to end', () {
    test('a connected laptop answers what the phone cannot', () async {
      final h = harness(FakeLaptop());
      await h.link.connect(good);

      final a = await h.router.ask('play my discover weekly');

      expect(a.tier, Tier.laptop);
      expect(a.text, 'Playing your playlist.');
    });

    test('on-device still wins even when the laptop is up', () async {
      final h = harness(FakeLaptop());
      await h.link.connect(good);

      final a = await h.router.ask('15% of 2400');
      expect(a.tier, Tier.device);
    });

    test('forgetting sends questions back to unanswered', () async {
      final h = harness(FakeLaptop());
      await h.link.connect(good);
      await h.link.forget();

      final a = await h.router.ask('play my discover weekly');
      expect(a.tier, Tier.none);
    });
  });
}
