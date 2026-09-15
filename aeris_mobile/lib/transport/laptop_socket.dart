import 'dart:async';

import 'package:web_socket_channel/web_socket_channel.dart';

import '../core/logger.dart';

/// The narrowest thing [LaptopTier] needs from a transport.
///
/// Deliberately not `WebSocketChannel` itself: a fake in a test should be five
/// lines, not a socket. Everything above this line is protocol, everything
/// below is plumbing.
abstract class LaptopSocket {
  Stream<String> get messages;

  void send(String text);

  Future<void> close();
}

typedef LaptopSocketFactory = Future<LaptopSocket> Function(Uri endpoint);

class WebSocketLaptopSocket implements LaptopSocket {
  WebSocketLaptopSocket(this._channel);

  final WebSocketChannel _channel;

  @override
  Stream<String> get messages =>
      _channel.stream.map((e) => e is String ? e : e.toString());

  @override
  void send(String text) => _channel.sink.add(text);

  @override
  Future<void> close() async {
    try {
      await _channel.sink.close();
    } catch (_) {
      // Already gone.
    }
  }
}

/// Opens a real WebSocket, waiting for the handshake to actually complete so a
/// refused connection surfaces here rather than as a stream error later.
Future<LaptopSocket> connectWebSocket(Uri endpoint) async {
  final channel = WebSocketChannel.connect(endpoint);
  await channel.ready;
  log.debug('laptop', 'socket open to $endpoint');
  return WebSocketLaptopSocket(channel);
}
