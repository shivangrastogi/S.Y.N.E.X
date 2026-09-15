import 'package:flutter/foundation.dart';

import '../brain/laptop_tier.dart';
import '../brain/router.dart';
import '../core/logger.dart';
import '../store/settings_store.dart';
import '../transport/pairing.dart';

enum LinkState {
  /// No pairing saved.
  unpaired,

  /// Deriving the key and opening the socket.
  connecting,

  /// Handshake done, questions can reach the laptop.
  connected,

  /// Paired but not reachable — laptop asleep, wrong passphrase, wrong network.
  failed,
}

/// Owns the laptop tier: pairing in, live connection out.
///
/// Separate from [AppSettings] because a pairing is data while a connection is
/// a resource with a lifecycle — conflating them makes it far too easy to leak
/// a socket every time a field changes.
class LaptopConnection extends ChangeNotifier {
  // The fields are private and the parameters are not, so initialising formals
  // cannot express this pairing without leaking underscores into the API.
  // ignore: prefer_initializing_formals
  LaptopConnection({
    required BrainRouter router,
    required SettingsStore store,
    LaptopTier Function(LaptopPairing, List<int>)? build,
  })  : _router = router,
        _store = store,
        _build = build ?? _realTier;

  final BrainRouter _router;
  final SettingsStore _store;
  final LaptopTier Function(LaptopPairing, List<int>) _build;

  static LaptopTier _realTier(LaptopPairing pairing, List<int> key) =>
      LaptopTier(
        endpoint: pairing.endpoint,
        // The passphrase authenticates as well as encrypts. The laptop compares
        // the token; the key proves the sender knew the same secret.
        token: pairing.passphrase,
        key: key,
      );

  LaptopPairing _pairing = LaptopPairing.none;
  LaptopPairing get pairing => _pairing;

  LinkState _state = LinkState.unpaired;
  LinkState get state => _state;

  String? _problem;

  /// Why the last attempt failed, in words a person can act on.
  String? get problem => _problem;

  LaptopTier? _tier;

  /// Loads a saved pairing and connects to it. Failure here is normal — the
  /// laptop is usually asleep — so it never throws.
  Future<void> restore() async {
    final saved = await _store.loadPairing();
    if (!saved.isConfigured) return;
    await connect(saved, persist: false);
  }

  /// Applies a pairing, saves it, and connects.
  Future<bool> connect(LaptopPairing pairing, {bool persist = true}) async {
    final problem = pairing.problem;
    if (problem != null) {
      _pairing = pairing;
      _set(LinkState.failed, problem);
      return false;
    }

    _detachTier();
    _pairing = pairing;
    _set(LinkState.connecting, null);

    try {
      // Deliberately slow (120k PBKDF2 rounds) — once per connect, never per
      // message, which is why it sits here and not in LaptopTier.ask.
      final key = await pairing.deriveKey();
      final tier = _build(pairing, key);
      final ok = await tier.connect();

      if (!ok) {
        tier.dispose();
        _set(
          LinkState.failed,
          'Could not reach ${pairing.host}. Check the laptop is awake, on the '
          'same Wi-Fi, and that A.E.R.I.S is running there.',
        );
        return false;
      }

      _tier = tier;
      _router.laptop = tier;
      if (persist) await _store.savePairing(pairing);
      _set(LinkState.connected, null);
      log.info('laptop', 'connected to ${pairing.host}');
      return true;
    } catch (e) {
      _set(LinkState.failed, 'Pairing failed: $e');
      return false;
    }
  }

  /// Forgets the pairing and closes the connection.
  Future<void> forget() async {
    _detachTier();
    _pairing = LaptopPairing.none;
    await _store.clearPairing();
    _set(LinkState.unpaired, null);
  }

  /// Retries the saved pairing — the button to press when the laptop wakes up.
  Future<bool> retry() async {
    if (!_pairing.isConfigured) return false;
    return connect(_pairing, persist: false);
  }

  void _detachTier() {
    _tier?.dispose();
    _tier = null;
    _router.laptop = null;
  }

  void _set(LinkState state, String? problem) {
    _state = state;
    _problem = problem;
    notifyListeners();
  }

  @override
  void dispose() {
    _detachTier();
    super.dispose();
  }
}
