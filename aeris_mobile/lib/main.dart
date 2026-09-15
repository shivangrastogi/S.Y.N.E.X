import 'dart:io' show Platform;

import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:flutter/material.dart';

import 'brain/router.dart';
import 'design/theme.dart';
import 'skills/builtin/builtins.dart';
import 'state/app_settings.dart';
import 'state/conversation.dart';
import 'store/settings_store.dart';
import 'store/transcript_store.dart';
import 'ui/chat_screen.dart';
import 'voice/device_voice.dart';
import 'voice/voice.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(const AerisApp());
}

/// True where the speech plugins actually have an implementation. Asking for
/// them on Windows throws `MissingPluginException`, so don't ask.
bool get _voiceSupported {
  if (kIsWeb) return false;
  return Platform.isAndroid || Platform.isIOS;
}

class AerisApp extends StatefulWidget {
  const AerisApp({super.key});

  @override
  State<AerisApp> createState() => _AerisAppState();
}

class _AerisAppState extends State<AerisApp> {
  late final _skills = defaultSkills();

  // The laptop and cloud tiers are not wired yet, so they are absent rather
  // than faked. The reach strip shows them dark, which is the truth.
  late final _router = BrainRouter(skills: _skills);
  late final _conversation =
      Conversation(_router, store: PrefsTranscriptStore());
  late final _settings = AppSettings(store: PrefsSettingsStore());

  late final VoiceIn _voiceIn = _voiceSupported ? DeviceVoiceIn() : SilentVoiceIn();
  late final VoiceOut _voiceOut =
      _voiceSupported ? DeviceVoiceOut() : SilentVoiceOut();

  bool _booted = false;

  @override
  void initState() {
    super.initState();
    _settings.addListener(_onSettings);
    _boot();
  }

  Future<void> _boot() async {
    // All of these are best-effort: a refused microphone permission, a missing
    // TTS engine, or an unreadable saved transcript each leave the app usable.
    await _settings.restore();
    await _conversation.restore();
    await _voiceIn.init();
    await _voiceOut.init();
    if (mounted) setState(() => _booted = true);
  }

  void _onSettings() {
    if (mounted) setState(() {});
  }

  @override
  void dispose() {
    _settings.removeListener(_onSettings);
    _voiceIn.dispose();
    _voiceOut.dispose();
    _conversation.dispose();
    _settings.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'A.E.R.I.S',
      debugShowCheckedModeBanner: false,
      theme: AerisTheme.light(),
      darkTheme: AerisTheme.dark(),
      themeMode: _settings.themeMode,
      home: ChatScreen(
        // Rebuilds once boot finishes, so the microphone appears only after it
        // is genuinely usable.
        key: ValueKey(_booted),
        conversation: _conversation,
        skills: _skills,
        voiceIn: _voiceIn,
        voiceOut: _voiceOut,
        settings: _settings,
      ),
    );
  }
}
