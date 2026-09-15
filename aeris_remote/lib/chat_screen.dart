import 'dart:async';
import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:speech_to_text/speech_to_text.dart';
import 'package:flutter_tts/flutter_tts.dart';
import 'package:permission_handler/permission_handler.dart';
import 'package:firebase_messaging/firebase_messaging.dart';
import 'bridge_client.dart';
import 'pairing.dart';
import 'pair_screen.dart';
import 'package:flutter_webrtc/flutter_webrtc.dart';
import 'phone_actions.dart';
import 'screen_capture.dart';
import 'lan_client.dart';
import 'webrtc_client.dart';
import 'phone_screen_sender.dart';
import 'file_transfer.dart';
import 'theme.dart';
import 'wake_controller.dart';
import 'wake_service.dart';
import 'assistant_settings.dart';
import 'phone_skills.dart';
import 'cloud_brain.dart';
import 'assistant_overlay.dart';
import 'aeris_log.dart';
import 'continuity.dart';

// Chat with AERIS from anywhere. Type or hold-to-talk (phone's native
// STT — the user's preferred Hinglish voice stack, on-device).
class ChatScreen extends StatefulWidget {
  final Pairing? pairing; // null = standalone (no laptop linked)
  final VoidCallback onUnpair;
  final ValueChanged<Pairing> onPaired;
  const ChatScreen(
      {super.key,
      required this.pairing,
      required this.onUnpair,
      required this.onPaired});

  @override
  State<ChatScreen> createState() => _ChatScreenState();
}

class _Msg {
  final String text;
  final bool fromMe;
  final Uint8List? image; // set for laptop screenshots/images
  final DateTime at = DateTime.now();
  _Msg(this.text, this.fromMe, {this.image});

  String get stamp {
    String two(int n) => n.toString().padLeft(2, '0');
    return '${two(at.hour)}:${two(at.minute)}';
  }
}

class _ChatScreenState extends State<ChatScreen>
    with WidgetsBindingObserver {
  BridgeClient? _bridge; // null when standalone (no laptop linked)
  final _input = TextEditingController();
  final _scroll = ScrollController();
  final _stt = SpeechToText();
  final FlutterTts _tts = FlutterTts();
  bool _lastWasVoice = false; // speak the reply only for voice commands
  final List<_Msg> _msgs = [];
  final PhoneFileTransfer _fileTx = PhoneFileTransfer();
  bool _online = false;
  bool _listening = false;
  bool _ringing = false;
  // Phase 4: live screen share.
  Uint8List? _laptopLiveFrame;   // non-null → laptop screen live overlay
  Timer? _phoneShareTimer;       // ticking while WE stream our screen
  bool _sharingPhone = false;
  bool _capturing = false;       // guards overlapping captures
  // Phase 4b: LAN fast-path + remote mouse.
  final LanClient _lan = LanClient();
  bool _lanConnected = false;
  bool _mouseMode = false;       // laptop overlay acts as a trackpad
  int _relayTick = 0;            // downsamples phone-share frames on relay
  int? _videoTextureId;          // non-null → 60fps H.264 texture active
  bool _videoStarting = false;   // stream announced, decoder warming up
  // Phase 5: WebRTC (remote-desktop grade mirroring).
  final WebRTCClient _webrtc = WebRTCClient();
  bool _webrtcConnected = false;
  String _webrtcStats = ''; // Phase 0: "58fps · 6.1Mb · 21ms" for the badge
  // Phase 5b: phone screen → laptop over WebRTC.
  final PhoneScreenSender _screenSender = PhoneScreenSender();
  // Phase 6: remote keyboard.
  bool _kbMode = false;
  final _kbCtrl = TextEditingController();
  final _kbFocus = FocusNode();
  String _kbPrev = '';
  // Phase 7: continuous two-way clipboard mirror. _clipLast holds the last
  // value we sent OR received so neither side echoes back. Android only lets
  // us read the clipboard while the app is foregrounded, so the poller pauses
  // in the background and resumes on resume.
  bool _clipSync = true;
  String _clipLast = '';
  Timer? _clipTimer;
  Timer? _beatTimer;             // continuity presence beats while app is up
  // Perceived-responsiveness: show AERIS "thinking" from send until the reply
  // lands (or a timeout, so a dropped reply doesn't hang the indicator).
  bool _awaiting = false;
  Timer? _awaitTimer;
  // Phase A1: hotword conversation mode. While true, each spoken reply is
  // followed by another listening turn; ends on silence / "sleep" / "ruko".
  bool _conversation = false;
  bool _cinematic = false; // full ignition (assist) vs compact (everyday wake)
  bool _turnRetryUsed = false; // one transient-STT-error retry per turn
  // Persistent "Jarvis" session: stays open + re-listens through silence until
  // the user says bye/bas. This is the last time anything actually happened —
  // used only as a battery safety to auto-close after a long dead silence.
  DateTime _lastActive = DateTime.now();
  static const _idleSafety = Duration(minutes: 3);
  Timer? _turnTimeout;
  late final void Function(Object) _wakeCb;
  // Phase A6: assist-gesture channel (power-button hold launches AERIS).
  static const _assistCh = MethodChannel('aeris/assist');
  // Phase A8: the full-screen voice HUD, mounted for the whole session.
  AssistantUiState _uiState = AssistantUiState.listening;
  double _amp = 0; // smoothed mic amplitude 0..1 (drives the visualizer)
  String _uiUser = '';
  String _uiReply = '';
  // Phase A9: recent Gemini turns so follow-ups keep context.
  final List<Map<String, String>> _history = [];

  Future<void> _registerPush() async {
    try {
      final token = await FirebaseMessaging.instance.getToken();
      if (token != null) await _bridge?.registerToken(token);
      // Ring pushes may arrive while the app is foregrounded too.
      FirebaseMessaging.onMessage.listen((m) {
        if ((m.data['action'] ?? '') == 'ring') {
          PhoneActions.ring();
          if (mounted) setState(() => _ringing = true);
        }
      });
    } catch (_) {}
  }

  Future<void> _stopRing() async {
    await PhoneActions.stopRing();
    if (mounted) setState(() => _ringing = false);
  }

  // ── Phase 4: stream OUR screen to the laptop ──────────────────────
  Future<void> _startPhoneShare() async {
    if (_sharingPhone) return;
    // First capture pops the OS screen-record dialog; bail if denied.
    if (!await ScreenCapture.ensurePermission()) {
      _add(_Msg('Screen-record permission chahiye — allow karo.', false));
      return;
    }
    if (mounted) setState(() => _sharingPhone = true);
    _phoneShareTimer?.cancel();
    // Fast cadence on LAN, gentle on the relay to protect the free quota.
    _phoneShareTimer =
        Timer.periodic(const Duration(milliseconds: 250), (_) async {
      if (!_sharingPhone || _capturing) return;
      // Relay path: throttle to ~1 frame / 1.3s; LAN path: every tick.
      if (!_lan.connected) {
        _relayTick++;
        if (_relayTick % 5 != 0) return; // 250ms * 5 ≈ 1.25s
      }
      _capturing = true;
      try {
        final bytes = await ScreenCapture.captureOnce();
        if (bytes != null) {
          if (_lan.connected) {
            _lan.sendPhoneFrame(bytes);
          } else {
            await _bridge?.send('Phone screen', type: 'phone_screen',
                extra: {'format': 'jpeg', 'b64': base64Encode(bytes)});
          }
        }
      } catch (_) {
      } finally {
        _capturing = false;
      }
    });
  }

  Future<void> _stopPhoneShare({bool notifyLaptop = true}) async {
    _phoneShareTimer?.cancel();
    _phoneShareTimer = null;
    if (mounted) setState(() => _sharingPhone = false);
    if (notifyLaptop) {
      // LAN first (instant + reliable), relay as fallback.
      _lan.sendControl('stop_phone_stream');
      await _bridge?.send('stop_phone_stream', type: 'control',
          extra: {'action': 'stop_phone_stream'});
    }
  }

  // ── Phase 4: exit the LAPTOP-screen live overlay ──────────────────
  Future<void> _exitLaptopLive() async {
    _webrtc.close();
    _kbFocus.unfocus();
    if (mounted) {
      setState(() {
        _laptopLiveFrame = null;
        _videoTextureId = null;
        _videoStarting = false;
        _webrtcConnected = false;
        _kbMode = false;
      });
    }
    // LAN first (instant + reliable), relay as fallback.
    _lan.sendControl('stop_laptop_stream');
    await _bridge?.send('stop_laptop_stream', type: 'control',
        extra: {'action': 'stop_laptop_stream'});
  }

  @override
  void initState() {
    super.initState();
    // Bridge only exists when a laptop is linked; standalone runs T1 + T3.
    if (widget.pairing != null) {
      _bridge = BridgeClient(widget.pairing!);
      _bridge!.startPresence();
      // Continuity: announce this body + pull the personal-facts slice so
      // Tier-3 (Gemini) answers know the user even with the laptop off.
      _startBeats();
      Continuity.requestMemory(_bridge!);
    }
    // LAN fast-path: laptop frames over the direct socket update the same
    // overlay the relay does, just far faster.
    _lan.onLaptopFrame = (bytes) {
      if (mounted) setState(() => _laptopLiveFrame = bytes);
    };
    _lan.onVideoStarting = () {
      if (mounted) setState(() => _videoStarting = true);
    };
    _lan.onVideoTexture = (id) {
      if (mounted) {
        setState(() {
          _videoTextureId = id;
          _videoStarting = false;
        });
      }
    };
    _lan.onStatus = (c) {
      if (mounted) {
        setState(() {
          _lanConnected = c;
          if (!c) {
            _videoTextureId = null;
            _videoStarting = false;
          }
        });
      }
    };
    // WebRTC (Phase 5) — remote-desktop mirroring.
    _webrtc.onAnswer = (ans) {
      _bridge?.send('', type: 'webrtc_answer', extra: ans);
    };
    _webrtc.onIce = (ice) {
      _bridge?.send('', type: 'webrtc_ice', extra: ice);
    };
    _webrtc.onConnected = () {
      if (mounted) {
        setState(() {
          _webrtcConnected = true;
          _videoStarting = false;
        });
      }
    };
    _webrtc.onClosed = () {
      if (mounted) setState(() => _webrtcConnected = false);
    };
    _webrtc.onStats = (line) {
      if (mounted) setState(() => _webrtcStats = line);
    };
    // Phone → laptop screen (WebRTC): we're the offerer.
    _screenSender.onOffer = (o) {
      _bridge?.send('', type: 'phone_webrtc_offer', extra: o);
      if (mounted) setState(() => _sharingPhone = true);
    };
    _screenSender.onIce = (ice) {
      _bridge?.send('', type: 'phone_webrtc_ice', extra: ice);
    };
    _screenSender.onClosed = () {
      if (mounted) setState(() => _sharingPhone = false);
    };
    // Control from the laptop over LAN (reliable, unlike the relay).
    _lan.onControl = (action) {
      if (action == 'stop_screen_stream') {
        _stopPhoneShare(notifyLaptop: false);
      } else if (action == 'stop_laptop_stream') {
        if (mounted) {
          setState(() {
            _laptopLiveFrame = null;
            _videoTextureId = null;
            _videoStarting = false;
          });
        }
      }
    };
    _bridge?.incoming().listen((m) {
      if (m.type == 'response' || m.type == 'chat') {
        _clearAwaiting();
        _add(_Msg(m.text, false));
        // Speak the reply back only when the command came in by voice.
        if (_lastWasVoice && m.text.trim().isNotEmpty) {
          _lastWasVoice = false;
          _sessionSpeak(m.text).then((_) {
            // Continuous conversation: reply spoken → next listening turn.
            if (_conversation && mounted) _listenTurn();
          });
        }
      } else if (m.type == 'event' && m.extra['env'] is Map) {
        // Continuity envelope from the mind: routed proactive speech
        // (reply.route → speak it HERE, this body is active) or a memory
        // slice (stored silently for the Tier-3 brain).
        Continuity.handleEnvelope(
                (m.extra['env'] as Map).cast<String, dynamic>())
            .then((reply) {
          if (reply != null && reply.isNotEmpty && mounted) {
            _add(_Msg(reply, false));
            _speak(reply);
          }
        });
      } else if (m.type == 'image') {
        // Laptop screenshot / image → show it inline.
        try {
          final bytes = base64Decode((m.extra['b64'] ?? '') as String);
          _add(_Msg(m.text.isEmpty ? 'Laptop image' : m.text, false,
              image: bytes));
        } catch (_) {}
      } else if (m.type == 'clipboard') {
        // Laptop clipboard → phone. Record it as last-seen first so the poller
        // won't bounce it back, then copy it silently (a toast, not a log
        // entry — continuous sync must not spam the transcript).
        _clipLast = m.text;
        Clipboard.setData(ClipboardData(text: m.text));
        final auto = m.extra['auto'] == true;
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(SnackBar(
            duration: Duration(seconds: auto ? 1 : 2),
            backgroundColor: A.panelHi,
            content: Text(
              '📋 Laptop se copy hua: '
              '${m.text.length > 40 ? '${m.text.substring(0, 40)}…' : m.text}',
              style: const TextStyle(color: A.text),
            ),
          ));
        }
      } else if (m.type == 'laptop_screen') {
        // Relay fallback frame (used only when LAN isn't connected).
        if (!_lanConnected) {
          try {
            final bytes = base64Decode((m.extra['b64'] ?? '') as String);
            if (mounted) setState(() => _laptopLiveFrame = bytes);
          } catch (_) {}
        }
      } else if (m.type == 'file_chunk') {
        // Laptop → phone file transfer → reassemble + save.
        _fileTx.onChunk(m.extra).then((path) {
          if (path != null) _add(_Msg('📥 File aayi + save ho gayi:\n$path', false));
        });
      } else if (m.type == 'webrtc_offer') {
        // Laptop offered a WebRTC screen session → answer it.
        if (mounted) setState(() => _videoStarting = true);
        _webrtc.handleOffer((m.extra['sdp'] ?? '') as String,
            iceServers: m.extra['ice'] as List?);
      } else if (m.type == 'webrtc_ice') {
        _webrtc.handleIce(Map<String, dynamic>.from(m.extra));
      } else if (m.type == 'phone_webrtc_answer') {
        _screenSender.handleAnswer((m.extra['sdp'] ?? '') as String);
      } else if (m.type == 'phone_webrtc_ice') {
        _screenSender.handleIce(Map<String, dynamic>.from(m.extra));
      } else if (m.type == 'lan_offer') {
        // Laptop handed us its LAN endpoints — race a direct connect.
        try {
          final ips = ((m.extra['ips'] ?? []) as List).cast<String>();
          final port = (m.extra['port'] as num?)?.toInt() ?? 0;
          final token = (m.extra['token'] ?? '') as String;
          if (ips.isNotEmpty && port > 0 && token.isNotEmpty) {
            _lan.connectFromOffer(ips, port, token);
          }
        } catch (_) {}
      } else if (m.type == 'phone_action') {
        final action = (m.extra['action'] ?? m.text).toString();
        if (action == 'start_phone_webrtc') {
          // Try smooth WebRTC first; if capture is denied or negotiation
          // can't start, fall back to the JPEG stream so the laptop still
          // sees something instead of a dead session.
          _screenSender.start(iceServers: m.extra['ice'] as List?).then((ok) {
            if (!ok && mounted) {
              _add(_Msg('WebRTC screen share nahi chala — '
                  'JPEG mode se bhej raha hoon.', false));
              _startPhoneShare();
            }
          });
        } else if (action == 'start_screen_stream') {
          _startPhoneShare();
        } else if (action == 'stop_screen_stream') {
          _screenSender.stop();
          _stopPhoneShare(notifyLaptop: false);
        } else {
          // ring / battery / one-shot request_screen.
          PhoneActions.handle(m, _bridge!);
          if (action == 'ring' && mounted) setState(() => _ringing = true);
        }
      }
    });
    _bridge?.laptopOnline().listen((v) {
      if (mounted) setState(() => _online = v);
    });
    // onStatus keeps the listening indicator honest: it mirrors the actual
    // engine state (start/auto-stop/timeouts), not just our intent to listen.
    // onError makes STT failures visible (A9) and retries ONE transient error
    // per turn so a stray no_match/busy doesn't kill the whole conversation.
    _stt.initialize(onStatus: (s) {
      if (!mounted) return;
      if (s == 'listening') {
        setState(() => _listening = true);
      } else if (s == 'notListening' || s == 'done') {
        setState(() => _listening = false);
        // Deadlock guard: a MANUAL (non-conversation) listen that ends with
        // no final result (silence/error) would otherwise never resume the
        // hotword — pauseMic ran, resumeMic only lived in onResult. Resume is
        // idempotent (service ignores it if the spotter is already up).
        if (!_conversation) WakeController.resumeMic();
      }
    }, onError: (e) {
      AerisLog.add('stt', e.errorMsg);
      const transient = {'error_no_match', 'error_busy',
        'error_speech_timeout', 'error_audio'};
      if (_conversation && mounted && !_turnRetryUsed &&
          transient.contains(e.errorMsg)) {
        _turnRetryUsed = true;
        Future.delayed(const Duration(milliseconds: 300), () {
          if (_conversation && mounted && !_listening) _listenTurn();
        });
      }
    });
    _initTts();
    if (_bridge != null) _registerPush(); // A10: no push work when standalone
    WidgetsBinding.instance.addObserver(this);
    _startClipSync();
    // Phase A1: hotword events. Warm app → data port; cold start → the
    // pending-wake flag the service set just before launching us.
    // Everyday "Aeris" wake → COMPACT (never takes over your screen).
    _wakeCb = (data) {
      if (data is Map && data['event'] == WakeEvents.wake) {
        _startConversation();
      }
    };
    WakeController.addListener(_wakeCb);
    WakeController.consumePendingWake().then((woke) {
      if (woke && mounted) _startConversation();
    });
    // Assist gesture (power-button hold) is a dedicated summon → CINEMATIC.
    _assistCh.setMethodCallHandler((call) async {
      if (call.method == 'assist' && mounted) {
        _startConversation(cinematic: true);
      }
    });
    _maybeAssist();
  }

  // Consume a pending assist launch (cold start / resume).
  Future<void> _maybeAssist() async {
    try {
      final v = await _assistCh.invokeMethod<bool>('consume');
      if (v == true && mounted) _startConversation(cinematic: true);
    } catch (_) {}
  }

  // ── Phase A1/A8: continuous conversation + voice HUD ──────────────
  Future<void> _startConversation({bool cinematic = false}) async {
    if (_conversation) return;
    _conversation = true;
    _cinematic = cinematic;
    _turnRetryUsed = false;
    // Tell the service we're holding the mic for the whole conversation —
    // cancels its crash-failsafe so it never restarts the hotword mid-turn.
    WakeController.pauseMic();
    // Open the HUD instantly in the "listening" state (don't wait for STT's
    // slower startup callback).
    if (mounted) {
      setState(() {
        _listening = true;
        _uiState = AssistantUiState.listening;
        _uiUser = '';
        _uiReply = '';
        _amp = 0;
      });
    }
    // The service already released the mic (it stops the spotter before
    // signalling us), so STT can start straight away.
    _listenTurn();
  }

  Future<void> _listenTurn() async {
    if (!_conversation || !mounted) return;
    if (!await Permission.microphone.request().isGranted) {
      _endConversation();
      return;
    }
    setState(() {
      _listening = true;
      _uiState = AssistantUiState.listening;
      _uiReply = '';
      _amp = 0;
    });
    var handled = false;
    // Persistent Jarvis mode: silence does NOT close the session — AERIS keeps
    // the panel open and re-listens for a follow-up. It only closes on "bye" /
    // "bas", or as a battery safety after a long dead silence (_idleSafety).
    _turnTimeout?.cancel();
    _turnTimeout = Timer(const Duration(seconds: 12), () {
      if (handled) return;
      handled = true;
      _stt.stop();
      if (!_conversation || !mounted) return;
      if (DateTime.now().difference(_lastActive) < _idleSafety) {
        _uiState = AssistantUiState.listening;
        _listenTurn(); // stay open, listen again
      } else {
        _endConversation(); // long dead silence → save battery (hotword armed)
      }
    });
    await _stt.listen(
      listenOptions: SpeechListenOptions(
          // Live partial words → the HUD fills in as you speak.
          partialResults: true,
          localeId: 'en_IN',
          listenFor: const Duration(seconds: 10),
          pauseFor: const Duration(seconds: 4)),
      // Real mic amplitude drives the HUD's reactive spokes.
      onSoundLevelChange: (level) {
        if (!mounted || !_conversation) return;
        final n = ((level + 2) / 12).clamp(0.0, 1.0);
        setState(() => _amp = _amp * 0.6 + n * 0.4);
      },
      onResult: (r) {
        if (handled) return;
        final words = r.recognizedWords.trim();
        // Show partials live; act only on the final result.
        if (!r.finalResult) {
          if (words.isNotEmpty && mounted && _conversation) {
            setState(() => _uiUser = words);
          }
          return;
        }
        handled = true;
        _turnRetryUsed = false; // a real result arrived — re-arm the retry
        _lastActive = DateTime.now(); // reset the idle-safety clock
        _turnTimeout?.cancel();
        if (mounted) setState(() => _listening = false);
        _handleVoiceCommand(words);
      },
    );
  }

  Future<void> _handleVoiceCommand(String words) async {
    if (words.isEmpty) {
      // Empty result — stay open and listen again (don't close on a blank).
      if (_conversation && mounted) _listenTurn();
      return;
    }
    final lower = words.toLowerCase();
    // Explicit goodbye → close the session (hotword stays armed for next time).
    if (RegExp(r'^(bye|bye bye|good ?bye|good ?night|khatam|tata|'
            r'chalo bye|ok bye|theek hai bye)$')
        .hasMatch(lower)) {
      _add(_Msg(words, true));
      await _sessionSpeak('Bye! Zarurat pade to "Aeris" bol dena.');
      _endConversation();
      return;
    }
    // "Aeris sleep" / "so jao" → hotword bhi band, notification se jagao.
    // Exact phrase only — "laptop ko sleep karo" laptop ka command hai,
    // AERIS ka nahi (one owner per phrase).
    if (RegExp(r'^(aeris\s+)?(sleep|so\s*jao?|soja|chale jao)$')
        .hasMatch(lower)) {
      _add(_Msg(words, true));
      await _speak('Theek hai, so raha hoon. Good night!');
      _conversation = false;
      if (mounted) setState(() => _listening = false);
      await WakeController.sleep();
      return;
    }
    // Dismissals → close the session, hotword stays armed.
    if (RegExp(r'^(bas|bus|ruko|rukja|stop|cancel|band karo|khatam|'
            r'kuch nahi|rehne do|never ?mind|thank(s| you).*)$')
        .hasMatch(lower)) {
      _endConversation();
      return;
    }
    // Everything else funnels through _send: Tier-1 phone skills first
    // (work offline), then the laptop, then an offline fallback.
    await _send(words, true);
  }

  void _endConversation() {
    _turnTimeout?.cancel();
    _conversation = false;
    if (mounted) setState(() => _listening = false);
    // Stop any in-progress speech BEFORE re-arming the hotword — else the
    // spotter resumes while AERIS is still talking and can wake on its own
    // voice (self-hearing). A short guard lets the audio tail drain so the
    // resumed mic doesn't catch the last word.
    _tts.stop();
    Future.delayed(const Duration(milliseconds: 500), () {
      if (!_conversation) WakeController.resumeMic();
    });
  }

  // ── Phase 7: continuous two-way clipboard mirror ──────────────────
  void _startClipSync() {
    _clipTimer?.cancel();
    if (!_clipSync) return;
    // Seed last-seen so we don't ship whatever was already on the clipboard.
    Clipboard.getData(Clipboard.kTextPlain).then((d) {
      _clipLast = d?.text ?? '';
    });
    _clipTimer = Timer.periodic(const Duration(milliseconds: 1400), (_) async {
      if (!_clipSync) return;
      try {
        final d = await Clipboard.getData(Clipboard.kTextPlain);
        final t = d?.text ?? '';
        if (t.isNotEmpty && t != _clipLast) {
          _clipLast = t;
          await _bridge?.send(t, type: 'set_clipboard',
              extra: {'text': t, 'auto': true});
        }
      } catch (_) {/* clipboard unreadable in background — ignore */}
    });
  }

  void _stopClipSync() {
    _clipTimer?.cancel();
    _clipTimer = null;
  }

  void _toggleClipSync() {
    setState(() => _clipSync = !_clipSync);
    if (_clipSync) {
      _startClipSync();
    } else {
      _stopClipSync();
    }
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(
      duration: const Duration(seconds: 2),
      backgroundColor: A.panelHi,
      content: Text(
        _clipSync
            ? '📋 Clipboard sync ON — dono taraf auto copy'
            : 'Clipboard sync OFF',
        style: const TextStyle(color: A.text),
      ),
    ));
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    // Android blocks clipboard reads in the background; pause + resume cleanly.
    if (state == AppLifecycleState.resumed) {
      _startClipSync();
      _startBeats(); // continuity: user is at the PHONE now
      _maybeAssist(); // assist gesture may have re-fired us
    } else if (state == AppLifecycleState.paused ||
        state == AppLifecycleState.inactive) {
      _stopClipSync();
      _stopBeats();
    }
  }

  /// Continuity presence: an immediate "active" beat + one every 60s while
  /// the app is foregrounded. On pause a single "idle" beat lets the mind
  /// fall back to laptop routing without waiting for staleness.
  void _startBeats() {
    if (_bridge == null) return;
    Continuity.sendBeat(_bridge!, 'active');
    _beatTimer?.cancel();
    _beatTimer = Timer.periodic(const Duration(seconds: 60), (_) {
      if (_bridge != null) Continuity.sendBeat(_bridge!, 'active');
    });
  }

  void _stopBeats() {
    _beatTimer?.cancel();
    _beatTimer = null;
    if (_bridge != null) Continuity.sendBeat(_bridge!, 'idle');
  }

  Future<void> _initTts() async {
    try {
      // Hinglish — match the en-IN STT the user speaks in.
      await _tts.setLanguage('en-IN');
      await _tts.setSpeechRate(0.5);
      await _tts.setPitch(1.0);
      await _tts.awaitSpeakCompletion(true);
    } catch (_) {}
  }

  Future<void> _speak(String text) async {
    try {
      // Keep Latin + Devanagari; drop emoji/symbols the engine can't say.
      final clean = text
          .replaceAll(RegExp(r'[^\x20-\x7Eऀ-ॿ]'), ' ')
          .replaceAll(RegExp(r'\s+'), ' ')
          .trim();
      if (clean.isEmpty) return;
      await _tts.stop();
      await _tts.speak(clean);
    } catch (_) {}
  }

  void _add(_Msg m) {
    setState(() => _msgs.add(m));
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_scroll.hasClients) {
        _scroll.animateTo(_scroll.position.maxScrollExtent,
            duration: const Duration(milliseconds: 200),
            curve: Curves.easeOut);
      }
    });
  }

  Future<void> _send([String? override, bool voice = false]) async {
    final text = (override ?? _input.text).trim();
    if (text.isEmpty) return;
    _lastWasVoice = voice; // only spoken commands get a spoken reply
    _input.clear();
    _add(_Msg(text, true));
    if (_conversation && mounted) {
      setState(() {
        _uiUser = text;
        _uiReply = '';
        _uiState = AssistantUiState.thinking;
      });
    }

    // Phase A7: an explicit "laptop pe …" always targets the PC (Tier-2),
    // even if the phrase also looks like a phone skill ("laptop pe chrome
    // kholo" must not open Chrome on the phone).
    final wantsLaptop = RegExp(r'\b(laptop|pc|computer|desktop)\b')
        .hasMatch(text.toLowerCase());

    // Tier-1: on-device phone skills (torch, call, app, alarm, WhatsApp…).
    // These need neither the laptop nor the internet, so they run first.
    final skill = wantsLaptop ? null : await PhoneSkills.handle(text);
    if (skill != null) {
      _add(_Msg(skill.spoken, false));
      if (voice) {
        await _sessionSpeak(skill.spoken);
        if (_conversation && mounted) _listenTurn(); // follow-up turn
      }
      return;
    }

    // Continuity: a standing intention ("follow up…", "nazar rakhna…")
    // goes to the mind as a typed goal.capture — the laptop's goal system
    // pursues it over time and the ack comes back as a normal response.
    if (_bridge != null && _online && Continuity.looksLikeGoal(text)) {
      _beginAwaiting();
      await Continuity.sendGoal(_bridge!, text);
      return;
    }

    // Tier-2: the laptop's full AERIS brain — only when one is linked and
    // reachable. Reply + speech happen in the incoming listener.
    if (_bridge != null && _online) {
      _beginAwaiting();
      await _bridge?.send(text);
      return;
    }

    // Tier-3: the cloud brain (Gemini) answers web/knowledge questions,
    // with recent turns for context so follow-ups work.
    if (await CloudBrain.isConfigured) {
      _beginAwaiting();
      final answer = await CloudBrain.ask(text, history: _history);
      _clearAwaiting();
      _history.add({'role': 'user', 'text': text});
      _history.add({'role': 'model', 'text': answer});
      if (_history.length > 8) {
        _history.removeRange(0, _history.length - 8);
      }
      _add(_Msg(answer, false));
      if (voice) {
        await _sessionSpeak(answer);
        if (_conversation && mounted) _listenTurn();
      }
      return;
    }

    // Nothing available for this one.
    const off = 'Iske liye laptop ya cloud brain chahiye. Assistant settings '
        'mein Gemini key daalo, ya laptop link karo.';
    _add(_Msg(off, false));
    if (voice) {
      await _sessionSpeak(off);
      // Stay open (persistent) — the user can ask something else or say "bye".
      if (_conversation && mounted) _listenTurn();
    }
  }

  // Speak within an active session: flip the HUD to "speaking" (mic is muted —
  // STT isn't running while AERIS talks), then speak. The caller re-opens the
  // next listening turn so the conversation stays continuous.
  Future<void> _sessionSpeak(String text) async {
    _lastActive = DateTime.now(); // AERIS speaking counts as activity
    if (_conversation && mounted) {
      setState(() {
        _uiReply = text;
        _uiState = AssistantUiState.speaking;
      });
    }
    await _speak(text);
  }

  void _beginAwaiting() {
    _awaitTimer?.cancel();
    setState(() => _awaiting = true);
    // Clear if the reply is lost (offline / relay hiccup) so it never hangs.
    // In a live session, don't close — re-listen (persistent until "bye").
    _awaitTimer = Timer(const Duration(seconds: 15), () {
      _clearAwaiting();
      if (_conversation && mounted) _listenTurn();
    });
  }

  void _clearAwaiting() {
    _awaitTimer?.cancel();
    _awaitTimer = null;
    if (_awaiting && mounted) setState(() => _awaiting = false);
  }

  // The input-bar mic opens the SAME compact assistant as a wake word — one
  // unified voice experience (frosted sheet, persistent, reactive core).
  Future<void> _toggleMic() async {
    if (_conversation) {
      _stt.stop();
      _endConversation();
    } else {
      _startConversation(); // compact
    }
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    WakeController.removeListener(_wakeCb);
    _turnTimeout?.cancel();
    _clipTimer?.cancel();
    _beatTimer?.cancel();
    _awaitTimer?.cancel();
    _phoneShareTimer?.cancel();
    _kbCtrl.dispose();
    _kbFocus.dispose();
    _tts.stop();
    _webrtc.dispose();
    _screenSender.stop();
    _lan.dispose();
    _bridge?.dispose();
    _input.dispose();
    _scroll.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Stack(children: [
      Scaffold(
        body: SafeArea(
          bottom: false,
          child: Column(
            children: [
              _header(),
              if (_ringing)
                _banner(
                  color: A.hot,
                  icon: Icons.notifications_active,
                  label: 'Ring baj rahi hai',
                  action: 'STOP',
                  onTap: _stopRing,
                ),
              if (_sharingPhone)
                _banner(
                  color: A.plasmaA,
                  icon: Icons.smartphone,
                  label: 'Phone screen laptop pe live',
                  action: 'STOP',
                  onTap: () => _stopPhoneShare(),
                ),
              _quickActions(),
              Expanded(
                child: _msgs.isEmpty && !_awaiting
                    ? _emptyState()
                    : ListView.builder(
                        controller: _scroll,
                        padding: const EdgeInsets.fromLTRB(14, 6, 14, 14),
                        itemCount: _msgs.length + (_awaiting ? 1 : 0),
                        itemBuilder: (_, i) => i < _msgs.length
                            ? _logEntry(_msgs[i])
                            : _thinkingRow(),
                      ),
              ),
              _inputBar(),
            ],
          ),
        ),
      ),
      if (_laptopLiveFrame != null ||
          _videoTextureId != null ||
          _videoStarting ||
          _webrtcConnected)
        _laptopLiveOverlay(),
      // Phase A8: the full-screen voice HUD — mounted for the whole session so
      // a turn never visibly closes; only the core's state changes.
      if (_conversation)
        AssistantOverlay(
          state: _uiState,
          mode: _cinematic
              ? AssistantMode.cinematic
              : AssistantMode.compact,
          userText: _uiUser,
          replyText: _uiReply,
          amplitude: _amp,
          online: _online,
          messages: [
            for (final m in (_msgs.length > 8
                ? _msgs.sublist(_msgs.length - 8)
                : _msgs))
              (text: m.text, fromMe: m.fromMe)
          ],
          onStop: () {
            _stt.stop();
            _endConversation();
          },
          onInterrupt: () {
            // Barge-in: cut AERIS off and listen right away.
            _tts.stop();
            if (_conversation && mounted) _listenTurn();
          },
        ),
    ]);
  }

  // Slim command-deck header: presence orb + wordmark + live status + menu.
  Widget _header() {
    return Container(
      padding: const EdgeInsets.fromLTRB(16, 10, 6, 10),
      decoration: const BoxDecoration(
        color: A.deck,
        border: Border(bottom: BorderSide(color: A.line)),
      ),
      child: Row(children: [
        AerisOrb(size: 34, online: _online, active: _listening),
        const SizedBox(width: 12),
        const Text(
          'AERIS',
          style: TextStyle(
            color: A.text,
            fontWeight: FontWeight.w800,
            letterSpacing: 3,
            fontSize: 16,
          ),
        ),
        const SizedBox(width: 12),
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 4),
          decoration: BoxDecoration(
            color: A.panel,
            borderRadius: BorderRadius.circular(20),
            border: Border.all(color: A.line),
          ),
          child: Row(mainAxisSize: MainAxisSize.min, children: [
            Container(
              width: 6,
              height: 6,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                color: _online ? A.plasmaC : A.faint,
              ),
            ),
            const SizedBox(width: 6),
            Text(
              _bridge == null
                  ? 'STANDALONE'
                  : (_online ? 'LAPTOP ONLINE' : 'LAPTOP OFFLINE'),
              style: TextStyle(
                fontFamily: A.mono,
                fontSize: 10,
                letterSpacing: 1.2,
                color: _online ? A.plasmaC : A.faint,
                fontWeight: FontWeight.w700,
              ),
            ),
          ]),
        ),
        const Spacer(),
        PopupMenuButton<String>(
          color: A.panelHi,
          icon: const Icon(Icons.more_vert, color: A.muted),
          onSelected: (v) async {
            if (v == 'unpair') {
              widget.onUnpair();
            } else if (v == 'pair') {
              await Navigator.of(context).push(MaterialPageRoute(
                  builder: (_) => PairScreen(onPaired: widget.onPaired)));
            } else if (v == 'assistant') {
              await Navigator.of(context).push(MaterialPageRoute(
                  builder: (_) => const AssistantSettingsScreen()));
            } else if (v == 'clip_sync') {
              _toggleClipSync();
            } else if (v == 'send_clip') {
              final d = await Clipboard.getData(Clipboard.kTextPlain);
              final t = (d?.text ?? '').trim();
              if (t.isNotEmpty) {
                await _bridge?.send(t, type: 'set_clipboard', extra: {'text': t});
                _add(_Msg('Clipboard laptop pe bhej diya', true));
              }
            } else if (v == 'send_file') {
              _add(_Msg('File chun raha hoon…', true));
              final name = await _fileTx.pickAndSend(_bridge!);
              if (name != null) {
                _add(_Msg('Bhej diya: $name (laptop ke ~/Downloads mein)', true));
              }
            }
          },
          itemBuilder: (_) => [
            const PopupMenuItem(
                value: 'assistant',
                child: _MenuRow(
                    Icons.record_voice_over, 'Assistant — "Aeris" hotword')),
            const PopupMenuDivider(),
            // Laptop features only when one is linked; else offer to link.
            if (_bridge == null)
              const PopupMenuItem(
                  value: 'pair',
                  child: _MenuRow(Icons.link, 'Link a laptop (optional)'))
            else ...[
              CheckedPopupMenuItem(
                value: 'clip_sync',
                checked: _clipSync,
                child: const Text('Clipboard sync (both ways)',
                    style: TextStyle(color: A.text, fontSize: 14)),
              ),
              const PopupMenuDivider(),
              const PopupMenuItem(
                  value: 'send_file',
                  child: _MenuRow(Icons.upload_file, 'Send a file to laptop')),
              const PopupMenuItem(
                  value: 'send_clip',
                  child:
                      _MenuRow(Icons.content_paste, 'Send my clipboard once')),
              const PopupMenuItem(
                  value: 'unpair',
                  child: _MenuRow(Icons.link_off, 'Unpair this laptop')),
            ],
          ],
        ),
      ]),
    );
  }

  Widget _banner({
    required Color color,
    required IconData icon,
    required String label,
    required String action,
    required VoidCallback onTap,
  }) {
    return Material(
      color: Colors.transparent,
      child: InkWell(
        onTap: onTap,
        child: Container(
          width: double.infinity,
          padding: const EdgeInsets.symmetric(vertical: 12, horizontal: 16),
          decoration: BoxDecoration(
            color: color.withValues(alpha: 0.14),
            border: Border(bottom: BorderSide(color: color.withValues(alpha: 0.5))),
          ),
          child: Row(children: [
            Icon(icon, color: color, size: 18),
            const SizedBox(width: 10),
            Expanded(
              child: Text(label,
                  style: TextStyle(color: color, fontWeight: FontWeight.w600)),
            ),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
              decoration: BoxDecoration(
                borderRadius: BorderRadius.circular(6),
                border: Border.all(color: color),
              ),
              child: Text(action,
                  style: TextStyle(
                      fontFamily: A.mono,
                      fontSize: 10,
                      letterSpacing: 1.5,
                      fontWeight: FontWeight.w700,
                      color: color)),
            ),
          ]),
        ),
      ),
    );
  }

  Widget _emptyState() {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const AerisOrb(size: 92, online: true),
            const SizedBox(height: 22),
            Text(
              _online ? 'AERIS sun raha hai.' : 'Laptop se connect ho raha…',
              style: const TextStyle(
                  color: A.text, fontSize: 17, fontWeight: FontWeight.w600),
            ),
            const SizedBox(height: 8),
            const Text(
              'Bolo ya likho — "laptop screen dikhao", "screenshot le",\n'
              '"battery kitni hai".',
              textAlign: TextAlign.center,
              style: TextStyle(color: A.muted, height: 1.5, fontSize: 13.5),
            ),
          ],
        ),
      ),
    );
  }

  // AERIS is working on the last command — shown until the reply lands.
  Widget _thinkingRow() {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 7),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text('AERIS',
              style: TextStyle(
                  fontFamily: A.mono,
                  fontSize: 10,
                  letterSpacing: 1.4,
                  fontWeight: FontWeight.w700,
                  color: A.plasmaB)),
          const SizedBox(height: 5),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 11),
            decoration: BoxDecoration(
              color: A.panel,
              borderRadius: const BorderRadius.only(
                topLeft: Radius.circular(14),
                topRight: Radius.circular(14),
                bottomLeft: Radius.circular(4),
                bottomRight: Radius.circular(14),
              ),
              border: Border.all(color: A.line),
            ),
            child: const Row(mainAxisSize: MainAxisSize.min, children: [
              AerisOrb(size: 20, online: true, active: true),
              SizedBox(width: 10),
              Text('soch raha hoon…',
                  style: TextStyle(color: A.muted, fontSize: 14)),
            ]),
          ),
        ],
      ),
    );
  }

  // ── remote mouse + keyboard helpers ───────────────────────────────
  // Both mouse and key events ride the same control channel.
  void _mouse(Map<String, dynamic> ev) {
    if (_webrtcConnected) {
      _webrtc.sendMouse(ev);
    } else if (_lan.connected) {
      _lan.sendMouse(ev);
    }
  }

  void _key(String key) => _mouse({'t': 'key', 'key': key});

  // The keyboard TextField changed — send the delta (typed chars or
  // backspaces) so typing on the phone lands on the laptop live.
  void _kbChanged(String v) {
    if (v.length > _kbPrev.length && v.startsWith(_kbPrev)) {
      _mouse({'t': 'type', 'text': v.substring(_kbPrev.length)});
    } else if (v.length < _kbPrev.length && _kbPrev.startsWith(v)) {
      for (int i = 0; i < _kbPrev.length - v.length; i++) {
        _key('backspace');
      }
    } else if (v != _kbPrev) {
      // Mixed edit (autocorrect/paste) — clear + retype the new content.
      final n = _kbPrev.length;
      for (int i = 0; i < n; i++) {
        _key('backspace');
      }
      if (v.isNotEmpty) _mouse({'t': 'type', 'text': v});
    }
    _kbPrev = v;
    // Keep the buffer short so the diff stays cheap.
    if (v.length > 120) {
      _kbCtrl.text = '';
      _kbPrev = '';
    }
  }

  void _kbEnter() {
    _key('enter');
    _kbCtrl.text = '';
    _kbPrev = '';
  }

  // Full-screen live view of the LAPTOP's screen + trackpad (Phase 4/4b).
  Widget _laptopLiveOverlay() {
    final Widget img = _webrtcConnected
        ? RTCVideoView(_webrtc.renderer,           // remote-desktop grade
            objectFit: RTCVideoViewObjectFit.RTCVideoViewObjectFitContain)
        : (_videoTextureId != null
            ? AspectRatio(                          // legacy 60fps H.264
                aspectRatio: _lan.videoAspect,
                child: Texture(textureId: _videoTextureId!))
            : (_laptopLiveFrame != null
                ? Image.memory(_laptopLiveFrame!,
                    gaplessPlayback: true, fit: BoxFit.contain)
                : const Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      AerisOrb(size: 76, online: true, active: true),
                      SizedBox(height: 18),
                      Text('Video connect ho raha hai…',
                          style: TextStyle(
                              fontFamily: A.mono,
                              fontSize: 12,
                              letterSpacing: 1,
                              color: A.muted)),
                    ],
                  )));

    // In mouse mode the image area is a trackpad; otherwise pinch-zoom view.
    final Widget canvas = _mouseMode
        ? GestureDetector(
            behavior: HitTestBehavior.opaque,
            onPanUpdate: (d) => _mouse({
              't': 'move',
              'dx': d.delta.dx * 2.0,
              'dy': d.delta.dy * 2.0,
            }),
            // No onDoubleTap: with onTap+onDoubleTap+pan on one detector,
            // Flutter eats double-taps and delays single taps 300ms. So we
            // fire an instant left-click on every tap — two quick taps then
            // become a real OS double-click (exactly like a laptop trackpad).
            onTap: () => _mouse({'t': 'click', 'b': 'left'}),
            onLongPress: () => _mouse({'t': 'click', 'b': 'right'}),
            child: Container(
                color: Colors.black,
                alignment: Alignment.center,
                child: img),
          )
        : InteractiveViewer(
            minScale: 1, maxScale: 4, child: Center(child: img));

    // Transport is real info — show which pipe is carrying the pixels, in mono.
    final String transport = _webrtcConnected
        ? 'WEBRTC'
        : (_videoTextureId != null
            ? 'LAN·60'
            : (_lanConnected ? 'LAN' : 'RELAY'));

    return Positioned.fill(
      child: Container(
        color: Colors.black,
        child: SafeArea(
          child: Column(
            children: [
              Container(
                width: double.infinity,
                padding:
                    const EdgeInsets.symmetric(vertical: 10, horizontal: 12),
                decoration: const BoxDecoration(
                  color: A.deck,
                  border: Border(bottom: BorderSide(color: A.line)),
                ),
                child: Row(
                  children: [
                    Container(
                      width: 8,
                      height: 8,
                      decoration: const BoxDecoration(
                        shape: BoxShape.circle,
                        gradient: A.plasma,
                      ),
                    ),
                    const SizedBox(width: 8),
                    const Text('LAPTOP',
                        style: TextStyle(
                            color: A.text,
                            fontWeight: FontWeight.w800,
                            letterSpacing: 1.5,
                            fontSize: 13)),
                    const SizedBox(width: 8),
                    Container(
                      padding: const EdgeInsets.symmetric(
                          horizontal: 7, vertical: 3),
                      decoration: BoxDecoration(
                        color: A.panel,
                        borderRadius: BorderRadius.circular(6),
                        border: Border.all(color: A.line),
                      ),
                      child: Text(
                          _webrtcConnected && _webrtcStats.isNotEmpty
                              ? '$transport · $_webrtcStats'
                              : transport,
                          style: const TextStyle(
                              fontFamily: A.mono,
                              fontSize: 10,
                              letterSpacing: 1,
                              color: A.plasmaC,
                              fontWeight: FontWeight.w700)),
                    ),
                    const Spacer(),
                    IconButton(
                      tooltip: 'Keyboard',
                      visualDensity: VisualDensity.compact,
                      onPressed: () {
                        setState(() => _kbMode = !_kbMode);
                        if (_kbMode) {
                          _kbCtrl.text = '';
                          _kbPrev = '';
                          Future.delayed(const Duration(milliseconds: 100),
                              () => _kbFocus.requestFocus());
                        } else {
                          _kbFocus.unfocus();
                        }
                      },
                      icon: Icon(Icons.keyboard,
                          color: _kbMode ? A.plasmaB : A.muted, size: 22),
                    ),
                    TextButton.icon(
                      onPressed: _exitLaptopLive,
                      style: TextButton.styleFrom(foregroundColor: A.hot),
                      icon: const Icon(Icons.close, size: 18),
                      label: const Text('Exit',
                          style: TextStyle(fontWeight: FontWeight.w700)),
                    ),
                  ],
                ),
              ),
              Expanded(child: canvas),
              if (_kbMode) _keyboardBar(),
              _mouseBar(),
            ],
          ),
        ),
      ),
    );
  }

  Widget _keyboardBar() {
    Widget special(String label, VoidCallback onTap) => Padding(
          padding: const EdgeInsets.symmetric(horizontal: 3),
          child: OutlinedButton(
            style: OutlinedButton.styleFrom(
              backgroundColor: A.panelHi,
              foregroundColor: A.text,
              minimumSize: const Size(0, 38),
              padding: const EdgeInsets.symmetric(horizontal: 12),
              side: const BorderSide(color: A.line),
              shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(9)),
            ),
            onPressed: onTap,
            child: Text(label,
                style: const TextStyle(fontSize: 12, fontFamily: A.mono)),
          ),
        );
    return Container(
      decoration: const BoxDecoration(
        color: A.panel,
        border: Border(top: BorderSide(color: A.line)),
      ),
      padding: const EdgeInsets.fromLTRB(8, 8, 8, 6),
      child: Column(mainAxisSize: MainAxisSize.min, children: [
        Row(children: [
          Expanded(
            child: TextField(
              controller: _kbCtrl,
              focusNode: _kbFocus,
              autofocus: true,
              onChanged: _kbChanged,
              onSubmitted: (_) => _kbEnter(),
              textInputAction: TextInputAction.done,
              style: const TextStyle(color: A.text),
              cursorColor: A.plasmaB,
              decoration: InputDecoration(
                isDense: true,
                hintText: 'Yahan type karo — laptop pe likhega',
                hintStyle: const TextStyle(color: A.faint),
                filled: true,
                fillColor: A.deck,
                contentPadding:
                    const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
                border: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(10),
                    borderSide: const BorderSide(color: A.line)),
                enabledBorder: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(10),
                    borderSide: const BorderSide(color: A.line)),
                focusedBorder: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(10),
                    borderSide: const BorderSide(color: A.plasmaB)),
              ),
            ),
          ),
          const SizedBox(width: 6),
          SizedBox(
            height: 44,
            width: 52,
            child: DecoratedBox(
              decoration: const BoxDecoration(
                gradient: A.plasma,
                borderRadius: BorderRadius.all(Radius.circular(10)),
              ),
              child: TextButton(
                onPressed: _kbEnter,
                child: const Icon(Icons.keyboard_return, color: A.deck, size: 20),
              ),
            ),
          ),
        ]),
        const SizedBox(height: 6),
        SingleChildScrollView(
          scrollDirection: Axis.horizontal,
          child: Row(children: [
            special('⌫', () => _key('backspace')),
            special('Tab', () => _key('tab')),
            special('Esc', () => _key('esc')),
            special('←', () => _key('left')),
            special('→', () => _key('right')),
            special('↑', () => _key('up')),
            special('↓', () => _key('down')),
            special('Ctrl+C', () => _mouse({'t': 'hotkey', 'keys': ['ctrl', 'c']})),
            special('Ctrl+V', () => _mouse({'t': 'hotkey', 'keys': ['ctrl', 'v']})),
            special('Win', () => _key('win')),
          ]),
        ),
      ]),
    );
  }

  Widget _mouseBar() {
    if (!_lanConnected && !_webrtcConnected) {
      return Container(
        width: double.infinity,
        decoration: const BoxDecoration(
          color: A.panel,
          border: Border(top: BorderSide(color: A.line)),
        ),
        padding: const EdgeInsets.symmetric(vertical: 12),
        child: const Text('Mouse control connect hone ke baad milega',
            textAlign: TextAlign.center,
            style: TextStyle(color: A.faint, fontSize: 12)),
      );
    }
    // Compact icon action (L/R click, scroll).
    Widget act(IconData icon, String label, VoidCallback onTap) => Expanded(
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 4),
            child: OutlinedButton(
              style: OutlinedButton.styleFrom(
                backgroundColor: A.panelHi,
                foregroundColor: A.text,
                padding: const EdgeInsets.symmetric(vertical: 10),
                side: const BorderSide(color: A.line),
                shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(10)),
              ),
              onPressed: onTap,
              child: Column(mainAxisSize: MainAxisSize.min, children: [
                Icon(icon, size: 18, color: A.plasmaB),
                const SizedBox(height: 2),
                Text(label,
                    style: const TextStyle(fontSize: 10, color: A.muted)),
              ]),
            ),
          ),
        );
    return Container(
      decoration: const BoxDecoration(
        color: A.deck,
        border: Border(top: BorderSide(color: A.line)),
      ),
      padding: const EdgeInsets.fromLTRB(8, 8, 8, 10),
      child: Column(mainAxisSize: MainAxisSize.min, children: [
        // Trackpad toggle — full-width pill so its label never crams.
        SizedBox(
          width: double.infinity,
          child: DecoratedBox(
            decoration: BoxDecoration(
              gradient: _mouseMode ? A.plasma : null,
              color: _mouseMode ? null : A.panel,
              borderRadius: BorderRadius.circular(12),
              border: Border.all(color: _mouseMode ? Colors.transparent : A.line),
            ),
            child: TextButton.icon(
              style: TextButton.styleFrom(
                foregroundColor: _mouseMode ? A.deck : A.text,
                padding: const EdgeInsets.symmetric(vertical: 13),
              ),
              onPressed: () => setState(() => _mouseMode = !_mouseMode),
              icon: Icon(_mouseMode ? Icons.touch_app : Icons.pan_tool_alt,
                  size: 18),
              label: Text(
                _mouseMode
                    ? 'Trackpad ON — ungli se cursor chalao'
                    : 'Trackpad OFF (View mode) — tap to enable',
                style: const TextStyle(fontWeight: FontWeight.w700),
              ),
            ),
          ),
        ),
        const SizedBox(height: 8),
        Row(children: [
          act(Icons.ads_click, 'Left', () => _mouse({'t': 'click', 'b': 'left'})),
          act(Icons.mouse_outlined, 'Right',
              () => _mouse({'t': 'click', 'b': 'right'})),
          act(Icons.keyboard_arrow_up, 'Scroll ↑',
              () => _mouse({'t': 'scroll', 'dy': 3})),
          act(Icons.keyboard_arrow_down, 'Scroll ↓',
              () => _mouse({'t': 'scroll', 'dy': -3})),
        ]),
      ]),
    );
  }

  Widget _quickActions() {
    const actions = <List<Object>>[
      [Icons.desktop_windows_outlined, 'Screen', 'laptop screen dikhao'],
      [Icons.stop_circle_outlined, 'Stop', 'screen share band karo'],
      [Icons.lock_outline, 'Lock', 'lock screen'],
      [Icons.photo_camera_outlined, 'Shot', 'take a screenshot'],
      [Icons.battery_5_bar_outlined, 'Battery', 'battery status'],
      [Icons.volume_down_outlined, 'Vol−', 'volume down'],
      [Icons.volume_up_outlined, 'Vol+', 'volume up'],
      [Icons.bedtime_outlined, 'Sleep', 'sleep pc'],
    ];
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(16, 12, 16, 8),
          child: A.label('quick commands'),
        ),
        SizedBox(
          height: 40,
          child: ListView.separated(
            scrollDirection: Axis.horizontal,
            padding: const EdgeInsets.symmetric(horizontal: 14),
            itemCount: actions.length,
            separatorBuilder: (_, __) => const SizedBox(width: 8),
            itemBuilder: (_, i) {
              final a = actions[i];
              return _CommandPill(
                icon: a[0] as IconData,
                label: a[1] as String,
                onTap: () => _send(a[2] as String),
              );
            },
          ),
        ),
        const SizedBox(height: 10),
      ],
    );
  }

  // A session-log entry — your commands and AERIS's replies, each tagged and
  // time-stamped in mono like a real console transcript.
  Widget _logEntry(_Msg m) {
    final me = m.fromMe;
    final tag = Row(
      mainAxisSize: MainAxisSize.min,
      mainAxisAlignment: me ? MainAxisAlignment.end : MainAxisAlignment.start,
      children: [
        Text(
          me ? 'YOU' : 'AERIS',
          style: TextStyle(
            fontFamily: A.mono,
            fontSize: 10,
            letterSpacing: 1.4,
            fontWeight: FontWeight.w700,
            color: me ? A.muted : A.plasmaB,
          ),
        ),
        const SizedBox(width: 8),
        Text(
          m.stamp,
          style: const TextStyle(
              fontFamily: A.mono, fontSize: 10, color: A.faint),
        ),
      ],
    );

    final body = Container(
      constraints:
          BoxConstraints(maxWidth: MediaQuery.of(context).size.width * 0.82),
      padding: m.image != null
          ? const EdgeInsets.all(6)
          : const EdgeInsets.symmetric(horizontal: 14, vertical: 11),
      decoration: BoxDecoration(
        color: me ? A.plasmaA.withValues(alpha: 0.12) : A.panel,
        borderRadius: BorderRadius.only(
          topLeft: const Radius.circular(14),
          topRight: const Radius.circular(14),
          bottomLeft: Radius.circular(me ? 14 : 4),
          bottomRight: Radius.circular(me ? 4 : 14),
        ),
        border: Border.all(color: me ? A.plasmaA.withValues(alpha: 0.35) : A.line),
      ),
      child: m.image != null
          ? Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                ClipRRect(
                  borderRadius: BorderRadius.circular(9),
                  child: Image.memory(m.image!, fit: BoxFit.contain),
                ),
                if (m.text.isNotEmpty)
                  Padding(
                    padding: const EdgeInsets.fromLTRB(8, 8, 8, 4),
                    child: Text(m.text,
                        style: const TextStyle(fontSize: 12.5, color: A.muted)),
                  ),
              ],
            )
          : Text(m.text,
              style: const TextStyle(height: 1.4, color: A.text, fontSize: 14.5)),
    );

    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 7),
      child: Column(
        crossAxisAlignment:
            me ? CrossAxisAlignment.end : CrossAxisAlignment.start,
        children: [
          tag,
          const SizedBox(height: 5),
          body,
        ],
      ),
    );
  }

  Widget _inputBar() {
    return Container(
      padding: EdgeInsets.fromLTRB(
          12, 10, 12, 12 + MediaQuery.of(context).padding.bottom),
      decoration: const BoxDecoration(
        color: A.deck,
        border: Border(top: BorderSide(color: A.line)),
      ),
      child: Column(mainAxisSize: MainAxisSize.min, children: [
        // Unmissable live-listening banner — appears the instant the mic is
        // hot, gone the instant it isn't (driven by the STT status stream).
        AnimatedSwitcher(
          duration: const Duration(milliseconds: 150),
          child: _listening
              ? Container(
                  key: const ValueKey('listening'),
                  width: double.infinity,
                  margin: const EdgeInsets.only(bottom: 10),
                  padding: const EdgeInsets.symmetric(vertical: 10),
                  decoration: BoxDecoration(
                    borderRadius: BorderRadius.circular(14),
                    color: A.plasmaB.withValues(alpha: 0.12),
                    border: Border.all(
                        color: A.plasmaB.withValues(alpha: 0.6)),
                  ),
                  child: const Row(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      AerisOrb(size: 22, online: true, active: true),
                      SizedBox(width: 10),
                      Text('SUN RAHA HOON…',
                          style: TextStyle(
                              color: A.plasmaB,
                              fontFamily: A.mono,
                              fontSize: 12,
                              letterSpacing: 2,
                              fontWeight: FontWeight.w700)),
                    ],
                  ),
                )
              : const SizedBox.shrink(key: ValueKey('idle')),
        ),
        Row(children: [
        Expanded(
          child: TextField(
            controller: _input,
            onSubmitted: (_) => _send(),
            textInputAction: TextInputAction.send,
            style: const TextStyle(color: A.text),
            cursorColor: A.plasmaB,
            decoration: InputDecoration(
              hintText: _listening ? 'Sun raha hoon…' : 'Bolo ya likho…',
              hintStyle: TextStyle(
                  color: _listening ? A.plasmaB : A.faint),
              filled: true,
              fillColor: A.panel,
              enabledBorder: OutlineInputBorder(
                borderRadius: BorderRadius.circular(24),
                borderSide: const BorderSide(color: A.line),
              ),
              focusedBorder: OutlineInputBorder(
                borderRadius: BorderRadius.circular(24),
                borderSide: const BorderSide(color: A.plasmaB, width: 1.4),
              ),
              contentPadding:
                  const EdgeInsets.symmetric(horizontal: 18, vertical: 13),
            ),
          ),
        ),
        const SizedBox(width: 10),
        // Mic — the presence orb; it wakes/pulses while listening.
        GestureDetector(
          onTap: _toggleMic,
          child: Container(
            width: 48,
            height: 48,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              color: A.panel,
              border: Border.all(
                  color: _listening ? A.hot : A.line, width: 1.4),
            ),
            child: _listening
                ? const Icon(Icons.stop_rounded, color: A.hot)
                : Center(child: AerisOrb(size: 34, online: _online)),
          ),
        ),
        const SizedBox(width: 8),
        // Send — plasma when there's something to send.
        GestureDetector(
          onTap: () => _send(),
          child: Container(
            width: 48,
            height: 48,
            decoration: const BoxDecoration(
              shape: BoxShape.circle,
              gradient: A.plasma,
            ),
            child: const Icon(Icons.arrow_upward_rounded, color: A.deck),
          ),
        ),
      ]),
      ]),
    );
  }
}

// A pill in the quick-commands rail: leading glyph + label, hairline framed.
class _CommandPill extends StatelessWidget {
  final IconData icon;
  final String label;
  final VoidCallback onTap;
  const _CommandPill(
      {required this.icon, required this.label, required this.onTap});

  @override
  Widget build(BuildContext context) {
    return Material(
      color: A.panel,
      borderRadius: BorderRadius.circular(20),
      child: InkWell(
        borderRadius: BorderRadius.circular(20),
        onTap: onTap,
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 14),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(20),
            border: Border.all(color: A.line),
          ),
          child: Row(mainAxisSize: MainAxisSize.min, children: [
            Icon(icon, size: 16, color: A.plasmaB),
            const SizedBox(width: 7),
            Text(label,
                style: const TextStyle(
                    color: A.text, fontSize: 13, fontWeight: FontWeight.w500)),
          ]),
        ),
      ),
    );
  }
}

class _MenuRow extends StatelessWidget {
  final IconData icon;
  final String label;
  const _MenuRow(this.icon, this.label);

  @override
  Widget build(BuildContext context) {
    return Row(children: [
      Icon(icon, size: 18, color: A.muted),
      const SizedBox(width: 12),
      Text(label, style: const TextStyle(color: A.text, fontSize: 14)),
    ]);
  }
}
