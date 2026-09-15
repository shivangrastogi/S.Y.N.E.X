import 'package:flutter/material.dart';
import 'package:firebase_core/firebase_core.dart';
import 'package:firebase_auth/firebase_auth.dart';
import 'package:firebase_messaging/firebase_messaging.dart';
import 'pairing.dart';
import 'chat_screen.dart';
import 'theme.dart';
import 'wake_controller.dart';

// FCM background handler — runs in its own isolate when a push arrives
// with the app closed/background. Must be a top-level function.
@pragma('vm:entry-point')
Future<void> _fcmBackground(RemoteMessage message) async {
  // The OS already shows the notification (which rings/vibrates). A full
  // loud-loop-when-closed needs a foreground service — the notification
  // is the MVP find-my-phone signal.
}

// AERIS Remote — control your laptop assistant from anywhere.
//
// Flow: anonymous Firebase sign-in → if paired, Chat; else Pair (QR scan).
// Firebase is initialised from android/app/google-services.json which the
// user adds via `flutterfire configure` (see aeris_remote/SETUP.md).
void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  // Wake-word service ↔ app port; restart the hotword if it was left on.
  WakeController.initPort();
  WakeController.ensureStarted();
  await Firebase.initializeApp();
  // Anonymous auth — the Firestore rules require request.auth != null.
  try {
    if (FirebaseAuth.instance.currentUser == null) {
      await FirebaseAuth.instance.signInAnonymously();
    }
  } catch (_) {/* offline start — retried on first send */}
  // Push: register the background handler + ask permission (Android 13+).
  try {
    FirebaseMessaging.onBackgroundMessage(_fcmBackground);
    await FirebaseMessaging.instance.requestPermission();
  } catch (_) {}
  runApp(const AerisRemoteApp());
}

class AerisRemoteApp extends StatelessWidget {
  const AerisRemoteApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'AERIS Remote',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        brightness: Brightness.dark,
        scaffoldBackgroundColor: A.deck,
        colorScheme: const ColorScheme.dark(
          primary: A.plasmaB,
          surface: A.panel,
          secondary: A.plasmaA,
          error: A.hot,
        ),
        splashFactory: InkSparkle.splashFactory,
        useMaterial3: true,
      ),
      home: const _Gate(),
    );
  }
}

/// Decides Pair vs Chat based on stored pairing.
class _Gate extends StatefulWidget {
  const _Gate();
  @override
  State<_Gate> createState() => _GateState();
}

class _GateState extends State<_Gate> {
  final _store = PairingStore();
  Pairing? _pairing;
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    final p = await _store.load();
    setState(() {
      _pairing = p;
      _loading = false;
    });
  }

  void _onPaired(Pairing p) async {
    await _store.save(p);
    setState(() => _pairing = p);
  }

  void _onUnpair() async {
    await _store.clear();
    setState(() => _pairing = null);
  }

  @override
  Widget build(BuildContext context) {
    if (_loading) {
      return const Scaffold(
        body: Center(child: AerisOrb(size: 88, online: true, active: true)),
      );
    }
    // Pairing is OPTIONAL now — AERIS opens straight into the assistant and
    // works standalone (phone skills + cloud brain). Linking a laptop just
    // adds Tier-2; it's offered from the in-app menu.
    // Key on the pairing id: pairing/unpairing mid-session must RECREATE the
    // ChatScreen State (the bridge is built in initState), else a fresh pair
    // never connects and an unpair leaves the old bridge running.
    return ChatScreen(
      key: ValueKey(_pairing?.pid ?? 'standalone'),
      pairing: _pairing,
      onPaired: _onPaired,
      onUnpair: _onUnpair,
    );
  }
}
