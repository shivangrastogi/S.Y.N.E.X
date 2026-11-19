// WebRTC client — the phone's side of core/webrtc_stream.py (Phase 5).
//
// The laptop is the offerer: it sends a `webrtc_offer` (SDP with its screen
// video track + a 'control' data channel) over the Firebase relay. We answer,
// trickle our ICE candidates back, and the video then flows peer-to-peer over
// UDP — remote-desktop smooth, adaptive, and not tied to same-WiFi or a cable.
import 'dart:async';
import 'dart:convert';
import 'package:flutter_webrtc/flutter_webrtc.dart';

class WebRTCClient {
  RTCPeerConnection? _pc;
  RTCDataChannel? _control; // reliable: clicks, keys, scroll, hotkeys
  RTCDataChannel? _mouse;   // lossy/unordered: cursor moves only
  // Phase 4: coalesce pan deltas and flush at ~125 Hz so we never queue a
  // burst of moves behind a slow link.
  Timer? _moveFlush;
  double _accDx = 0, _accDy = 0;
  final RTCVideoRenderer renderer = RTCVideoRenderer();
  bool _rendererReady = false;
  bool get connected => _pc != null;

  // Phase 0: live stats for the transport badge (e.g. "58fps · 6.1Mb · 21ms").
  Timer? _statsTimer;
  int _lastBytes = 0;
  DateTime _lastStatsAt = DateTime.now();
  void Function(String line)? onStats;

  /// Send our SDP answer back to the laptop (over the relay).
  void Function(Map<String, dynamic> answer)? onAnswer;

  /// Trickle one of our ICE candidates to the laptop.
  void Function(Map<String, dynamic> ice)? onIce;

  /// The remote video track arrived — the UI can show the renderer now.
  void Function()? onConnected;

  /// Session ended / failed.
  void Function()? onClosed;

  static const _defaultIce = {
    'iceServers': [
      {'urls': 'stun:stun.l.google.com:19302'},
    ],
  };

  Future<void> _ensureRenderer() async {
    if (!_rendererReady) {
      await renderer.initialize();
      _rendererReady = true;
    }
  }

  /// Handle a laptop offer → build the peer connection + answer.
  /// [iceServers] (optional) mirrors the laptop's STUN/TURN list so both
  /// sides can use the same relay for cross-NAT connections.
  Future<void> handleOffer(String sdp, {List? iceServers}) async {
    await close();
    await _ensureRenderer();
    final cfg = (iceServers != null && iceServers.isNotEmpty)
        ? {'iceServers': iceServers}
        : _defaultIce;
    final pc = await createPeerConnection(cfg);
    _pc = pc;

    pc.onIceCandidate = (c) {
      if (c.candidate != null) {
        onIce?.call({
          'candidate': c.candidate,
          'sdpMid': c.sdpMid,
          'sdpMLineIndex': c.sdpMLineIndex,
        });
      }
    };
    pc.onTrack = (RTCTrackEvent e) {
      if (e.track.kind == 'video' && e.streams.isNotEmpty) {
        renderer.srcObject = e.streams[0];
        onConnected?.call();
      }
    };
    pc.onDataChannel = (ch) {
      // Keep each laptop-created channel by its label (Phase 4).
      if (ch.label == 'mouse') {
        _mouse = ch;
      } else {
        _control = ch;
      }
    };
    pc.onConnectionState = (s) {
      if (s == RTCPeerConnectionState.RTCPeerConnectionStateFailed ||
          s == RTCPeerConnectionState.RTCPeerConnectionStateClosed ||
          s == RTCPeerConnectionState.RTCPeerConnectionStateDisconnected) {
        onClosed?.call();
      }
    };

    await pc.setRemoteDescription(RTCSessionDescription(sdp, 'offer'));
    final answer = await pc.createAnswer();
    await pc.setLocalDescription(answer);
    onAnswer?.call({'sdp': answer.sdp, 'type': answer.type});
    _startStats();
  }

  void _startStats() {
    _statsTimer?.cancel();
    _lastBytes = 0;
    _lastStatsAt = DateTime.now();
    _statsTimer = Timer.periodic(const Duration(seconds: 2), (_) async {
      final pc = _pc;
      if (pc == null || onStats == null) return;
      try {
        final reports = await pc.getStats();
        num fps = 0, bytes = 0, rttMs = 0;
        for (final r in reports) {
          final v = r.values;
          if (r.type == 'inbound-rtp' && (v['kind'] == 'video' ||
              v['mediaType'] == 'video')) {
            fps = (v['framesPerSecond'] as num?) ?? fps;
            bytes = (v['bytesReceived'] as num?) ?? bytes;
          } else if (r.type == 'candidate-pair' &&
              (v['nominated'] == true || v['state'] == 'succeeded')) {
            final rtt = v['currentRoundTripTime'] as num?;
            if (rtt != null) rttMs = (rtt * 1000).round();
          }
        }
        final now = DateTime.now();
        final dt = now.difference(_lastStatsAt).inMilliseconds / 1000.0;
        num mbps = 0;
        if (_lastBytes > 0 && dt > 0) {
          mbps = (bytes - _lastBytes) * 8 / dt / 1e6;
        }
        _lastBytes = bytes.toInt();
        _lastStatsAt = now;
        onStats?.call('${fps.round()}fps · '
            '${mbps.toStringAsFixed(1)}Mb · ${rttMs.round()}ms');
      } catch (_) {}
    });
  }

  Future<void> handleIce(Map<String, dynamic> ice) async {
    try {
      await _pc?.addCandidate(RTCIceCandidate(
        ice['candidate'] as String?,
        ice['sdpMid'] as String?,
        (ice['sdpMLineIndex'] as num?)?.toInt(),
      ));
    } catch (_) {}
  }

  /// Drive the laptop mouse/keyboard. Cursor MOVES are accumulated and flushed
  /// on the lossy 'mouse' channel at ~125 Hz (dropping a move is fine); every
  /// other event (click/key/scroll) goes reliably + immediately on 'control'.
  void sendMouse(Map<String, dynamic> ev) {
    if (ev['t'] == 'move') {
      final m = _mouse;
      if (m == null || m.state != RTCDataChannelState.RTCDataChannelOpen) {
        return; // no lossy channel yet → drop the move, never queue it
      }
      _accDx += (ev['dx'] as num?)?.toDouble() ?? 0;
      _accDy += (ev['dy'] as num?)?.toDouble() ?? 0;
      _moveFlush ??= Timer.periodic(const Duration(milliseconds: 8), (_) {
        if (_accDx == 0 && _accDy == 0) return;
        final mc = _mouse;
        if (mc != null && mc.state == RTCDataChannelState.RTCDataChannelOpen) {
          mc.send(RTCDataChannelMessage(
              jsonEncode({'t': 'move', 'dx': _accDx, 'dy': _accDy})));
        }
        _accDx = 0;
        _accDy = 0;
      });
      return;
    }
    final ch = _control;
    if (ch != null && ch.state == RTCDataChannelState.RTCDataChannelOpen) {
      ch.send(RTCDataChannelMessage(jsonEncode(ev)));
    }
  }

  Future<void> close() async {
    _statsTimer?.cancel();
    _statsTimer = null;
    _moveFlush?.cancel();
    _moveFlush = null;
    _accDx = _accDy = 0;
    _control = null;
    _mouse = null;
    try {
      renderer.srcObject = null;
    } catch (_) {}
    final pc = _pc;
    _pc = null;
    try {
      await pc?.close();
    } catch (_) {}
  }

  Future<void> dispose() async {
    await close();
    try {
      await renderer.dispose();
    } catch (_) {}
    _rendererReady = false;
  }
}
