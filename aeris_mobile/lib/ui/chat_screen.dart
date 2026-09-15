import 'package:flutter/material.dart';

import '../core/logger.dart';
import '../design/theme.dart';
import '../design/tokens.dart';
import '../skills/skill.dart';
import '../state/app_settings.dart';
import '../state/conversation.dart';
import '../voice/voice.dart';
import 'diagnostics_screen.dart';
import 'settings_screen.dart';
import 'widgets/link_strip.dart';
import 'widgets/message_bubble.dart';

class ChatScreen extends StatefulWidget {
  const ChatScreen({
    super.key,
    required this.conversation,
    required this.skills,
    required this.voiceIn,
    required this.voiceOut,
    this.settings,
  });

  final Conversation conversation;
  final Skills skills;
  final VoiceIn voiceIn;
  final VoiceOut voiceOut;

  /// Absent in tests that only care about the transcript; the settings button
  /// is hidden when there is nothing to configure.
  final AppSettings? settings;

  @override
  State<ChatScreen> createState() => _ChatScreenState();
}

class _ChatScreenState extends State<ChatScreen> {
  final _input = TextEditingController();
  final _inputFocus = FocusNode();
  final _scroll = ScrollController();

  bool _listening = false;

  @override
  void initState() {
    super.initState();
    widget.conversation.addListener(_onTurn);
  }

  @override
  void dispose() {
    widget.conversation.removeListener(_onTurn);
    _input.dispose();
    _inputFocus.dispose();
    _scroll.dispose();
    super.dispose();
  }

  void _onTurn() {
    if (!mounted) return;
    setState(() {});
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!_scroll.hasClients || !mounted) return;
      final target = _scroll.position.maxScrollExtent;
      // Reduced motion applies to scrolling too — jump rather than glide.
      if (MediaQuery.of(context).disableAnimations) {
        _scroll.jumpTo(target);
        return;
      }
      _scroll.animateTo(
        target,
        duration: const Duration(milliseconds: 220),
        curve: Curves.easeOut,
      );
    });
  }

  Future<void> _send({String? preset, bool spoken = false}) async {
    final text = preset ?? _input.text;
    if (text.trim().isEmpty) return;

    // A new turn cancels whatever the last one was still saying.
    await widget.voiceOut.stop();

    _input.clear();
    if (!spoken) _inputFocus.requestFocus();

    final answer = await widget.conversation.send(text);

    // Speak only when the question was spoken. Typing at an assistant in a
    // quiet room and having it talk back is a bug, not a feature.
    if (spoken && answer != null && mounted) {
      await widget.voiceOut.speak(answer.text);
    }
  }

  void _openDiagnostics() {
    Navigator.of(context).push(
      MaterialPageRoute<void>(
        builder: (_) => DiagnosticsScreen(
          log: log,
          skillCount: widget.skills.all.length,
          messageCount: widget.conversation.messages.length,
        ),
      ),
    );
  }

  void _openSettings() {
    final settings = widget.settings;
    if (settings == null) return;
    Navigator.of(context).push(
      MaterialPageRoute<void>(
        builder: (_) => SettingsScreen(settings: settings),
      ),
    );
  }

  Future<void> _toggleMic() async {
    if (_listening) {
      await widget.voiceIn.stop();
      if (mounted) setState(() => _listening = false);
      return;
    }

    // Stop speaking first, or the recogniser hears A.E.R.I.S and transcribes it.
    await widget.voiceOut.stop();
    _inputFocus.unfocus();
    setState(() => _listening = true);

    await widget.voiceIn.start((text, isFinal) {
      if (!mounted) return;
      _input.value = TextEditingValue(
        text: text,
        selection: TextSelection.collapsed(offset: text.length),
      );
      if (isFinal) {
        setState(() => _listening = false);
        if (text.trim().isNotEmpty) _send(spoken: true);
      } else {
        setState(() {});
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    final p = AerisPalette.of(context);
    final convo = widget.conversation;

    return Scaffold(
      appBar: AppBar(
        backgroundColor: p.surface,
        elevation: 0,
        titleSpacing: T.s4,
        title: Text(
          'A.E.R.I.S',
          style: AerisTheme.readout(context, color: p.ink, size: 14),
        ),
        actions: [
          if (!convo.isEmpty)
            TextButton(
              onPressed: () {
                widget.voiceOut.stop();
                convo.clear();
              },
              child: Text('Clear', style: AerisTheme.readout(context, size: 11)),
            ),
          IconButton(
            onPressed: _openDiagnostics,
            icon: const Icon(Icons.monitor_heart_outlined, size: 20),
            color: p.inkDim,
            tooltip: 'Diagnostics',
          ),
          if (widget.settings != null)
            IconButton(
              onPressed: _openSettings,
              icon: const Icon(Icons.tune, size: 20),
              color: p.inkDim,
              tooltip: 'Settings',
            ),
        ],
      ),
      body: Column(
        children: [
          LinkStrip(reach: convo.reach),
          Expanded(
            child: convo.isEmpty
                ? _EmptyState(
                    skills: widget.skills,
                    onPick: (text) => _send(preset: text),
                  )
                : ListView.builder(
                    controller: _scroll,
                    padding: const EdgeInsets.fromLTRB(T.s4, T.s4, T.s4, T.s2),
                    itemCount: convo.messages.length,
                    itemBuilder: (context, i) =>
                        MessageBubble(message: convo.messages[i]),
                  ),
          ),
          _Composer(
            controller: _input,
            focusNode: _inputFocus,
            enabled: !convo.isBusy,
            listening: _listening,
            micAvailable: widget.voiceIn.isAvailable,
            onSend: () => _send(),
            onMic: _toggleMic,
          ),
        ],
      ),
    );
  }
}

/// An empty screen is an invitation to act, so it shows what actually works
/// offline right now rather than a logo and a greeting.
class _EmptyState extends StatelessWidget {
  const _EmptyState({required this.skills, required this.onPick});

  final Skills skills;
  final void Function(String) onPick;

  @override
  Widget build(BuildContext context) {
    final p = AerisPalette.of(context);
    final examples = [
      for (final s in skills.all)
        if (s.examples.isNotEmpty) (s.name, s.examples.first),
    ];

    return ListView(
      padding: const EdgeInsets.all(T.s5),
      children: [
        Text('Works without the laptop',
            style: Theme.of(context).textTheme.titleMedium),
        const SizedBox(height: T.s1),
        Text(
          'These run on the phone. Everything else waits for a laptop or cloud link.',
          style: Theme.of(context).textTheme.bodySmall,
        ),
        const SizedBox(height: T.s4),
        for (final (skillName, example) in examples)
          Padding(
            padding: const EdgeInsets.only(bottom: T.s2),
            child: InkWell(
              borderRadius: BorderRadius.circular(T.radiusSm),
              onTap: () => onPick(example),
              child: Container(
                padding: const EdgeInsets.symmetric(
                  horizontal: T.s3,
                  vertical: T.s3 - 2,
                ),
                decoration: BoxDecoration(
                  color: p.surface,
                  border: Border.all(color: p.line),
                  borderRadius: BorderRadius.circular(T.radiusSm),
                ),
                child: Row(
                  children: [
                    Expanded(
                      child: Text(example,
                          style: Theme.of(context).textTheme.bodyMedium),
                    ),
                    const SizedBox(width: T.s2),
                    Text(skillName.toUpperCase(),
                        style: AerisTheme.readout(context, size: 9.5)),
                  ],
                ),
              ),
            ),
          ),
      ],
    );
  }
}

class _Composer extends StatelessWidget {
  const _Composer({
    required this.controller,
    required this.focusNode,
    required this.enabled,
    required this.listening,
    required this.micAvailable,
    required this.onSend,
    required this.onMic,
  });

  final TextEditingController controller;
  final FocusNode focusNode;
  final bool enabled;
  final bool listening;
  final bool micAvailable;
  final VoidCallback onSend;
  final VoidCallback onMic;

  @override
  Widget build(BuildContext context) {
    final p = AerisPalette.of(context);

    return Container(
      padding: const EdgeInsets.fromLTRB(T.s3, T.s2, T.s3, T.s3),
      decoration: BoxDecoration(
        color: p.surface,
        border: Border(top: BorderSide(color: p.line)),
      ),
      child: SafeArea(
        top: false,
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            if (listening)
              Padding(
                padding: const EdgeInsets.only(bottom: T.s2),
                child: Row(
                  children: [
                    _PulseDot(color: p.tierDevice),
                    const SizedBox(width: T.s2),
                    Text(
                      'LISTENING',
                      style: AerisTheme.readout(context, color: p.tierDevice),
                    ),
                    const Spacer(),
                    Text(
                      'TAP TO STOP',
                      style: AerisTheme.readout(context, size: 9.5),
                    ),
                  ],
                ),
              ),
            Row(
              crossAxisAlignment: CrossAxisAlignment.end,
              children: [
                if (micAvailable) ...[
                  IconButton(
                    onPressed: enabled ? onMic : null,
                    icon: Icon(listening ? Icons.stop : Icons.mic_none, size: 22),
                    color: listening ? p.tierDevice : p.inkDim,
                    tooltip: listening ? 'Stop listening' : 'Speak',
                    style: IconButton.styleFrom(
                      minimumSize: const Size(44, 44),
                    ),
                  ),
                  const SizedBox(width: T.s1),
                ],
                Expanded(
                  child: TextField(
                    controller: controller,
                    focusNode: focusNode,
                    enabled: enabled,
                    minLines: 1,
                    maxLines: 4,
                    textInputAction: TextInputAction.send,
                    onSubmitted: (_) => onSend(),
                    style: Theme.of(context).textTheme.bodyLarge,
                    decoration: InputDecoration(
                      hintText: listening ? 'Listening…' : 'Ask A.E.R.I.S',
                      hintStyle: Theme.of(context).textTheme.bodySmall,
                      filled: true,
                      fillColor: p.surfaceHi,
                      contentPadding: const EdgeInsets.symmetric(
                        horizontal: T.s4,
                        vertical: T.s3,
                      ),
                      border: OutlineInputBorder(
                        borderRadius: BorderRadius.circular(T.radius),
                        borderSide: BorderSide.none,
                      ),
                    ),
                  ),
                ),
                const SizedBox(width: T.s2),
                IconButton.filled(
                  onPressed: enabled ? onSend : null,
                  icon: const Icon(Icons.arrow_upward, size: 20),
                  style: IconButton.styleFrom(
                    backgroundColor: p.tierDevice,
                    foregroundColor: p.ground,
                    minimumSize: const Size(44, 44),
                  ),
                  tooltip: 'Send',
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

/// A slow pulse while the microphone is open — the one place in the app where
/// motion is load-bearing, because "am I being heard" needs an answer at a glance.
class _PulseDot extends StatefulWidget {
  const _PulseDot({required this.color});
  final Color color;

  @override
  State<_PulseDot> createState() => _PulseDotState();
}

class _PulseDotState extends State<_PulseDot>
    with SingleTickerProviderStateMixin {
  late final AnimationController _c = AnimationController(
    vsync: this,
    duration: const Duration(milliseconds: 900),
  );

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    final still = MediaQuery.of(context).disableAnimations;
    if (still && _c.isAnimating) {
      _c.stop();
    } else if (!still && !_c.isAnimating) {
      _c.repeat(reverse: true);
    }
  }

  @override
  void dispose() {
    _c.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: _c,
      builder: (context, _) => Container(
        width: 8,
        height: 8,
        decoration: BoxDecoration(
          shape: BoxShape.circle,
          color: widget.color.withValues(alpha: 0.4 + _c.value * 0.6),
        ),
      ),
    );
  }
}
