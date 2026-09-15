// Phone → laptop screen over WebRTC (Phase 5b). The phone captures its own
// screen (getDisplayMedia / Android MediaProjection) and streams it as a
// WebRTC video track to the laptop — smooth, unlike the old JPEG polling.
//
// The phone is the OFFERER here: getDisplayMedia → add track → createOffer →
// send `phone_webrtc_offer`; the laptop answers (`phone_webrtc_answer`).
import 'package:flutter/services.dart';
import 'package:flutter_webrtc/flutter_webrtc.dart';

class PhoneScreenSender {
  // Same channel MainActivity uses for the JPEG path — here just to start/stop
  // the mediaProjection foreground service that Android 14+ requires before
  // getDisplayMedia can capture the screen.
  static const _screencap = MethodChannel('aeris/screencap');

  RTCPeerConnection? _pc;
  MediaStream? _stream;
  bool _serviceUp = false;

  void Function(Map<String, dynamic> offer)? onOffer;
  void Function(Map<String, dynamic> ice)? onIce;
  void Function()? onClosed;

  List _ice = const [
    {'urls': 'stun:stun.l.google.com:19302'},
  ];

  bool get active => _pc != null;

  /// Capture the screen and offer it to the laptop.
  Future<bool> start({List? iceServers}) async {
    await stop();
    if (iceServers != null && iceServers.isNotEmpty) _ice = iceServers;
    // Android 14+: a mediaProjection foreground service MUST be running before
    // getDisplayMedia captures, else the plugin hard-crashes the app. Start it
    // first; if the OS refuses, capture just fails and we return false.
    try {
      final ok = await _screencap.invokeMethod('startScreenService');
      _serviceUp = ok == true;
    } catch (_) {
      _serviceUp = false;
    }
    try {
      // Pops the system screen-record consent dialog on Android. Ask for 60fps
      // + a moderate size so text stays crisp without flooding the link.
      _stream = await navigator.mediaDevices.getDisplayMedia({
        'video': {
          'frameRate': {'ideal': 60, 'max': 60},
          'width': {'ideal': 1280},
          'height': {'ideal': 1280},
        },
        'audio': false,
      });
      // (contentHint 'detail' would sharpen text, but flutter_webrtc 0.12.x
      // doesn't expose that setter — the maxBitrate bump below covers crispness.)
    } catch (_) {
      await _stopService();
      return false;
    }
    final pc = await createPeerConnection({'iceServers': _ice});
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
    pc.onConnectionState = (s) {
      if (s == RTCPeerConnectionState.RTCPeerConnectionStateFailed ||
          s == RTCPeerConnectionState.RTCPeerConnectionStateClosed) {
        onClosed?.call();
      }
    };
    for (final track in _stream!.getTracks()) {
      await pc.addTrack(track, _stream!);
    }
    // Raise the encoder ceiling so the phone stream can climb to a crisp
    // bitrate/framerate (defaults cap low). Guarded — parameter support varies.
    try {
      final senders = await pc.getSenders();
      for (final s in senders) {
        if (s.track?.kind != 'video') continue;
        final p = s.parameters;
        if (p.encodings != null && p.encodings!.isNotEmpty) {
          p.encodings![0].maxBitrate = 8 * 1000 * 1000; // 8 Mbps
          p.encodings![0].maxFramerate = 60;
          await s.setParameters(p);
        }
      }
    } catch (_) {}
    final offer = await pc.createOffer();
    await pc.setLocalDescription(offer);
    onOffer?.call({'sdp': offer.sdp, 'type': offer.type});
    return true;
  }

  Future<void> handleAnswer(String sdp) async {
    try {
      await _pc?.setRemoteDescription(RTCSessionDescription(sdp, 'answer'));
    } catch (_) {}
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

  Future<void> stop() async {
    try {
      _stream?.getTracks().forEach((t) => t.stop());
      await _stream?.dispose();
    } catch (_) {}
    _stream = null;
    final pc = _pc;
    _pc = null;
    try {
      await pc?.close();
    } catch (_) {}
    await _stopService();
  }

  Future<void> _stopService() async {
    if (!_serviceUp) return;
    _serviceUp = false;
    try {
      await _screencap.invokeMethod('stopScreenService');
    } catch (_) {}
  }
}
