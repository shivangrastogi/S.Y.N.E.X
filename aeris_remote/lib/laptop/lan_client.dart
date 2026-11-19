// LAN fast-path client — the phone's side of core/lan_link.py.
//
// When the laptop sends a `lan_offer` (its LAN IPs + port + a session token,
// itself delivered E2E-encrypted over the bridge), we race a direct TCP
// connect to each IP. On success we get ~20-50ms frames + can drive the
// laptop mouse — no Firebase in the loop. If nothing connects (different
// network), the app just keeps using the relay.
//
// Framing after an `AERIS <token>\n` / `OK\n` handshake:
//   1 type byte + 4-byte big-endian length + payload
//     'L' laptop→phone  JPEG laptop frame
//     'I' laptop→phone  video info JSON {w,h,fps,codec}
//     'V' laptop→phone  H.264 access unit
//     'C' both ways     control JSON {"action": ...}
//     'P' phone→laptop  JPEG phone frame
//     'M' phone→laptop  mouse JSON
import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';
import 'video_decoder.dart';

class LanClient {
  Socket? _sock;
  int _curPort = 0; // port of the current connection (dedupe redundant offers)

  // Handshake state — we listen immediately after connecting and parse the
  // one-line "OK\n" reply inside _onData (using Stream.first on a raw Socket
  // is fragile: it's single-subscription and can swallow the first frame).
  bool _handshaking = false;
  Completer<bool>? _hs;
  final _hsBuf = BytesBuilder();

  final _buf = BytesBuilder();
  int _need = -1; // payload length once header parsed, else -1
  int _type = 0;
  bool _connecting = false;

  final VideoDecoder _video = VideoDecoder();
  bool _videoInit = false;
  double videoAspect = 16 / 9; // laptop screen w/h, from the video info

  /// Fired with each decoded laptop-screen JPEG frame (fallback mode).
  void Function(Uint8List jpeg)? onLaptopFrame;

  /// Fired when a live H.264 texture is ready (textureId) or torn down (null).
  void Function(int? textureId)? onVideoTexture;

  /// Fired the moment a video stream is announced (before the texture is
  /// ready) so the UI can open the overlay with a spinner.
  void Function()? onVideoStarting;

  /// Fired for a control message from the laptop over LAN ('C').
  void Function(String action)? onControl;

  /// Fired when the direct connection opens/closes.
  void Function(bool connected)? onStatus;

  bool get connected => _sock != null;

  /// Try every advertised IP; keep the first socket that handshakes.
  Future<bool> connectFromOffer(
      List<String> ips, int port, String token) async {
    // Already connected to THIS server (same port) → keep the working socket.
    // A fresh offer with a NEW port means the laptop restarted its server, so
    // the old socket is dead and we must reconnect. This dedupe is what stops
    // the reconnect churn that tore down a live stream on every offer.
    if (_sock != null && _curPort == port) return true;
    if (_connecting) return false;
    _connecting = true;
    try {
      _drop();
      for (final ip in ips) {
        Socket? s;
        try {
          s = await Socket.connect(ip, port,
              timeout: const Duration(milliseconds: 1200));
          _handshaking = true;
          _hsBuf.clear();
          _hs = Completer<bool>();
          final sock = s;
          s.listen(_onData,
              onDone: () => _onClose(sock),
              onError: (_) => _onClose(sock),
              cancelOnError: true);
          s.add(utf8.encode('AERIS $token\n'));
          await s.flush();
          bool ok = false;
          try {
            ok = await _hs!.future.timeout(const Duration(seconds: 3));
          } catch (_) {
            ok = false;
          }
          if (ok) {
            _sock = s;
            _curPort = port;
            onStatus?.call(true);
            return true;
          }
          _handshaking = false;
          s.destroy();
        } catch (_) {
          try {
            s?.destroy();
          } catch (_) {}
        }
      }
      return false;
    } finally {
      _connecting = false;
    }
  }

  void _onClose(Socket s) {
    if (_handshaking && !(_hs?.isCompleted ?? true)) {
      _handshaking = false;
      _hs?.complete(false);
    }
    if (identical(s, _sock)) _drop();
  }

  void _onData(Uint8List data) {
    if (_handshaking) {
      _hsBuf.add(data);
      final b = _hsBuf.toBytes();
      final nl = b.indexOf(10); // '\n'
      if (nl < 0) return; // wait for the rest of the handshake line
      final line = utf8.decode(b.sublist(0, nl), allowMalformed: true).trim();
      _handshaking = false;
      final ok = line == 'OK';
      if (!(_hs?.isCompleted ?? true)) _hs?.complete(ok);
      if (!ok) return;
      // Anything after the newline is already frame data.
      if (nl + 1 < b.length) _feedFrames(Uint8List.sublistView(b, nl + 1));
      return;
    }
    _feedFrames(data);
  }

  void _feedFrames(Uint8List data) {
    _buf.add(data);
    final bytes = _buf.toBytes();
    var off = 0;
    while (true) {
      if (_need < 0) {
        if (bytes.length - off < 5) break;
        _type = bytes[off];
        _need = (bytes[off + 1] << 24) |
            (bytes[off + 2] << 16) |
            (bytes[off + 3] << 8) |
            bytes[off + 4];
        off += 5;
      }
      if (bytes.length - off < _need) break;
      final payload = Uint8List.sublistView(bytes, off, off + _need);
      off += _need;
      final t = _type;
      _need = -1;
      if (t == 0x56 /* 'V' */) {
        if (_videoInit) _video.feed(Uint8List.fromList(payload));
      } else if (t == 0x4C /* 'L' */) {
        onLaptopFrame?.call(Uint8List.fromList(payload));
      } else if (t == 0x49 /* 'I' */) {
        _onVideoInfo(payload);
      } else if (t == 0x43 /* 'C' — control */) {
        _onControl(payload);
      }
    }
    _buf.clear();
    if (off < bytes.length) _buf.add(Uint8List.sublistView(bytes, off));
  }

  void _onControl(Uint8List payload) {
    try {
      final m = jsonDecode(utf8.decode(payload)) as Map<String, dynamic>;
      final a = (m['action'] ?? '') as String;
      if (a.isNotEmpty) onControl?.call(a);
    } catch (_) {}
  }

  // Video info {w,h,fps,codec} → (re)create the native decoder + texture.
  Future<void> _onVideoInfo(Uint8List payload) async {
    try {
      final info = jsonDecode(utf8.decode(payload)) as Map<String, dynamic>;
      final w = (info['w'] as num?)?.toInt() ?? 0;
      final h = (info['h'] as num?)?.toInt() ?? 0;
      if (w <= 0 || h <= 0) return;
      videoAspect = w / h;
      onVideoStarting?.call();
      if (_videoInit) {
        _videoInit = false;
        await _video.dispose();
      }
      final id = await _video.init(w, h);
      _videoInit = id != null;
      onVideoTexture?.call(id);
    } catch (_) {}
  }

  void _send(int type, List<int> payload) {
    final s = _sock;
    if (s == null) return;
    final n = payload.length;
    final hdr = Uint8List(5);
    hdr[0] = type;
    hdr[1] = (n >> 24) & 0xFF;
    hdr[2] = (n >> 16) & 0xFF;
    hdr[3] = (n >> 8) & 0xFF;
    hdr[4] = n & 0xFF;
    try {
      s.add(hdr);
      s.add(payload);
    } catch (_) {
      _drop();
    }
  }

  /// Send a phone-screen frame to the laptop (bypasses Firebase).
  void sendPhoneFrame(Uint8List jpeg) => _send(0x50 /* 'P' */, jpeg);

  /// Send a mouse event to the laptop.
  void sendMouse(Map<String, dynamic> ev) =>
      _send(0x4D /* 'M' */, utf8.encode(jsonEncode(ev)));

  /// Send a control action to the laptop over LAN (reliable, unlike relay).
  void sendControl(String action) =>
      _send(0x43 /* 'C' */, utf8.encode(jsonEncode({'action': action})));

  void _drop() {
    final s = _sock;
    _sock = null;
    _curPort = 0;
    _need = -1;
    _buf.clear();
    if (_videoInit) {
      _videoInit = false;
      _video.dispose();
      onVideoTexture?.call(null);
    }
    try {
      s?.destroy();
    } catch (_) {}
    if (s != null) onStatus?.call(false);
  }

  void dispose() => _drop();
}
