import 'dart:async';
import 'dart:convert';

import '../core/logger.dart';
import '../transport/crypto.dart';
import '../transport/laptop_socket.dart';
import 'tier.dart';

/// Talks to the full A.E.R.I.S brain on the laptop.
///
/// ## Wire protocol
///
/// 1. Open a WebSocket to the laptop, LAN only.
/// 2. Send the plaintext line `AERIS <token>` — same handshake shape as
///    `core/lan_link.py`, so the laptop can reuse its pairing logic.
/// 3. Laptop replies `OK` or `NO`. `NO` means the token was wrong; do not retry.
/// 4. Everything after that is an AES-256-GCM envelope `{"n":…,"ct":…}`, the
///    exact format `core/cloud_bridge.py` already speaks.
///
/// Requests carry an `id` and replies echo it, so a slow answer cannot be
/// delivered to the wrong question — which matters here, because the user can
/// ask again while the first is still in flight.
///
/// The token is not decoration. The laptop end runs skills, and skills open
/// apps and drive the PC, so an unauthenticated endpoint is remote code
/// execution. Bind it to the LAN and check the token before anything else.
class LaptopTier implements TierHandler {
  LaptopTier({
    required this.endpoint,
    required this.token,
    required List<int> key,
    LaptopSocketFactory? connect,
    this.timeout = const Duration(seconds: 6),
  })  : _crypto = BridgeCrypto(key),
        _connect = connect ?? connectWebSocket;

  final Uri endpoint;
  final String token;

  /// How long to wait for one answer before giving up and letting the router
  /// fall through. Generous for a LAN, short enough not to strand the user.
  final Duration timeout;

  final BridgeCrypto _crypto;
  final LaptopSocketFactory _connect;

  LaptopSocket? _socket;
  StreamSubscription<String>? _sub;
  Completer<bool>? _handshake;
  final Map<String, Completer<String?>> _pending = {};
  int _nextId = 0;
  bool _ready = false;

  /// True once the handshake has succeeded and the socket is still open.
  @override
  bool get isAvailable => _ready;

  @override
  Tier get tier => Tier.laptop;

  /// Opens the socket and completes the handshake. Safe to call repeatedly;
  /// returns the existing connection when one is already up.
  Future<bool> connect() async {
    if (_ready) return true;
    if (_handshake != null) return _handshake!.future;

    final done = Completer<bool>();
    _handshake = done;

    try {
      final socket = await _connect(endpoint);
      _socket = socket;
      _sub = socket.messages.listen(
        _onMessage,
        onError: (Object e) => _drop('socket error: $e'),
        onDone: () => _drop('laptop closed the connection'),
        cancelOnError: false,
      );
      socket.send('AERIS $token');
    } catch (e) {
      log.info('laptop', 'could not reach $endpoint: $e');
      _handshake = null;
      if (!done.isCompleted) done.complete(false);
      return false;
    }

    // Don't hang for ever on a host that accepts the socket then says nothing.
    return done.future.timeout(timeout, onTimeout: () {
      _drop('handshake timed out');
      return false;
    });
  }

  @override
  Future<String?> ask(String text) async {
    if (!_ready && !await connect()) return null;

    final id = '${_nextId++}';
    final waiting = Completer<String?>();
    _pending[id] = waiting;

    try {
      final envelope = await _crypto.encrypt({
        'cmd': 'ask',
        'id': id,
        'text': text,
      });
      _socket!.send(jsonEncode(envelope));
    } catch (e) {
      _pending.remove(id);
      log.error('laptop', 'could not send: $e');
      return null;
    }

    return waiting.future.timeout(timeout, onTimeout: () {
      _pending.remove(id);
      log.warn('laptop', 'no reply within ${timeout.inSeconds}s');
      return null;
    });
  }

  Future<void> _onMessage(String raw) async {
    // Handshake first: the only two plaintext frames in the protocol.
    if (!_ready) {
      final reply = raw.trim();
      if (reply == 'OK') {
        _ready = true;
        log.info('laptop', 'paired with $endpoint');
        _handshake?.complete(true);
      } else {
        // NO, or anything unexpected. A wrong token is not worth retrying.
        _drop(reply == 'NO' ? 'laptop rejected the token' : 'bad handshake: $reply');
      }
      _handshake = null;
      return;
    }

    Map<String, dynamic>? payload;
    try {
      final decoded = jsonDecode(raw);
      if (decoded is Map<String, dynamic>) {
        payload = await _crypto.decrypt(decoded);
      }
    } catch (_) {
      payload = null;
    }

    if (payload == null) {
      // Wrong key or a tampered frame. Dropping it quietly is correct — the
      // pending request will time out and the router moves on.
      log.warn('laptop', 'undecryptable frame dropped');
      return;
    }

    final id = payload['id'];
    final waiting = id is String ? _pending.remove(id) : null;
    if (waiting == null) {
      log.debug('laptop', 'reply for an unknown request, ignored');
      return;
    }

    final reply = payload['reply'];
    waiting.complete(reply is String && reply.trim().isNotEmpty ? reply : null);
  }

  /// Tears the connection down and fails everything in flight, so no caller is
  /// left waiting on a socket that is gone.
  void _drop(String why) {
    if (_ready || _pending.isNotEmpty) log.info('laptop', why);
    _ready = false;
    _sub?.cancel();
    _sub = null;
    _socket?.close();
    _socket = null;

    if (_handshake != null && !_handshake!.isCompleted) {
      _handshake!.complete(false);
    }
    _handshake = null;

    for (final waiting in _pending.values) {
      if (!waiting.isCompleted) waiting.complete(null);
    }
    _pending.clear();
  }

  void dispose() => _drop('disposed');
}
