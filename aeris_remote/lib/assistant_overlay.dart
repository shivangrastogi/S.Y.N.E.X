// The AERIS voice interface. Two experiences, one arc-reactor (reactor_painter):
//   • cinematic — full-screen ignition boot (app-open / power-button assist /
//     first launch). The grand "wow" moment.
//   • compact   — a small live core docked at the bottom for everyday "Aeris"
//     wake, so it never takes over what you were doing (Google-like, but AERIS).
// The reactor's spokes react to REAL mic amplitude; state colours it
// listening(cyan) → thinking(violet) → speaking(mint).
import 'dart:ui' as ui;
import 'package:flutter/material.dart';
import 'theme.dart';
import 'reactor_painter.dart';

enum AssistantUiState { listening, thinking, speaking }

enum AssistantMode { cinematic, compact }

class AssistantOverlay extends StatefulWidget {
  final AssistantUiState state;
  final AssistantMode mode;
  final String userText;
  final String replyText;
  final double amplitude;
  final bool online;
  final List<({String text, bool fromMe})> messages; // recent turns (compact)
  final VoidCallback onStop;
  final VoidCallback onInterrupt;

  const AssistantOverlay({
    super.key,
    required this.state,
    required this.mode,
    required this.userText,
    required this.replyText,
    required this.amplitude,
    required this.online,
    required this.messages,
    required this.onStop,
    required this.onInterrupt,
  });

  @override
  State<AssistantOverlay> createState() => _AssistantOverlayState();
}

class _AssistantOverlayState extends State<AssistantOverlay>
    with TickerProviderStateMixin {
  late final AnimationController _frames; // per-frame rebuild driver
  late final AnimationController _ign; // ignition 0..1
  final Stopwatch _sw = Stopwatch()..start(); // continuous seconds

  @override
  void initState() {
    super.initState();
    _frames = AnimationController(
        vsync: this, duration: const Duration(seconds: 2))
      ..repeat();
    _ign = AnimationController(
      vsync: this,
      duration: Duration(
          milliseconds: widget.mode == AssistantMode.cinematic ? 1650 : 420),
    );
    final reduce = WidgetsBinding
        .instance.platformDispatcher.accessibilityFeatures.disableAnimations;
    if (reduce) {
      _ign.value = 1;
    } else {
      _ign.forward();
    }
  }

  @override
  void dispose() {
    _frames.dispose();
    _ign.dispose();
    super.dispose();
  }

  Color get _accent => switch (widget.state) {
        AssistantUiState.listening => Reactor.arc,
        AssistantUiState.thinking => Reactor.violet,
        AssistantUiState.speaking => Reactor.mint,
      };

  String get _label => switch (widget.state) {
        AssistantUiState.listening => 'SUN RAHA HOON',
        AssistantUiState.thinking => 'SOCH RAHA HOON',
        AssistantUiState.speaking => 'AERIS BOL RAHA HAI',
      };

  Widget _reactor(double dim) => GestureDetector(
        onTap: widget.state == AssistantUiState.speaking
            ? widget.onInterrupt
            : null,
        child: AnimatedBuilder(
          animation: Listenable.merge([_frames, _ign]),
          builder: (_, __) => CustomPaint(
            size: Size.square(dim),
            painter: _ReactorPaint(
              t: _sw.elapsedMilliseconds / 1000.0,
              ign: _ign.value,
              amp: widget.amplitude,
              accent: _accent,
            ),
          ),
        ),
      );

  @override
  Widget build(BuildContext context) {
    return widget.mode == AssistantMode.cinematic
        ? _buildCinematic(context)
        : _buildCompact(context);
  }

  // ── everyday wake: Google-Assistant-style frosted sheet — the screen
  // behind blurs, the sheet grows with the conversation, and it stays open
  // (persistent "Jarvis") until you say bye. ───────────────────────────
  Widget _buildCompact(BuildContext context) {
    final live = widget.state == AssistantUiState.speaking
        ? widget.replyText
        : widget.userText;
    final maxH = MediaQuery.of(context).size.height * 0.66;
    return Positioned.fill(
      child: Stack(children: [
        // blurred, dimmed backdrop — your screen stays visible behind it.
        // Tapping the dim area ends the session.
        GestureDetector(
          onTap: widget.onStop,
          child: BackdropFilter(
            filter: ui.ImageFilter.blur(sigmaX: 16, sigmaY: 16),
            child: Container(color: A.deck.withValues(alpha: 0.32)),
          ),
        ),
        // the sheet, docked to the bottom, sized to its content up to maxH.
        Positioned(
          left: 0,
          right: 0,
          bottom: 0,
          child: TweenAnimationBuilder<double>(
            tween: Tween(begin: 44, end: 0),
            duration: const Duration(milliseconds: 300),
            curve: Curves.easeOutCubic,
            builder: (_, dy, child) =>
                Transform.translate(offset: Offset(0, dy), child: child),
            child: ClipRRect(
              borderRadius:
                  const BorderRadius.vertical(top: Radius.circular(26)),
              child: BackdropFilter(
                filter: ui.ImageFilter.blur(sigmaX: 30, sigmaY: 30),
                child: Container(
                  constraints: BoxConstraints(maxHeight: maxH),
                  decoration: BoxDecoration(
                    color: A.panel.withValues(alpha: 0.92), // crisp chats
                    border: Border(
                        top: BorderSide(
                            color: _accent.withValues(alpha: 0.55),
                            width: 1.4)),
                  ),
                  child: SafeArea(
                    top: false,
                    child: Column(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        const SizedBox(height: 10),
                        Container(
                            width: 38,
                            height: 4,
                            decoration: BoxDecoration(
                                color: A.line,
                                borderRadius: BorderRadius.circular(2))),
                        // conversation — grows, then scrolls at maxH
                        if (widget.messages.isNotEmpty)
                          Flexible(
                            child: ListView.builder(
                              padding: const EdgeInsets.fromLTRB(16, 12, 16, 4),
                              shrinkWrap: true,
                              reverse: true,
                              itemCount: widget.messages.length,
                              itemBuilder: (_, i) {
                                final m = widget
                                    .messages[widget.messages.length - 1 - i];
                                return _bubble(m.text, m.fromMe);
                              },
                            ),
                          ),
                        _reactorRow(live),
                        SizedBox(
                            height: 12 +
                                MediaQuery.of(context).padding.bottom * 0),
                      ],
                    ),
                  ),
                ),
              ),
            ),
          ),
        ),
      ]),
    );
  }

  Widget _bubble(String text, bool fromMe) => Align(
        alignment: fromMe ? Alignment.centerRight : Alignment.centerLeft,
        child: Container(
          margin: const EdgeInsets.symmetric(vertical: 4),
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
          constraints: BoxConstraints(
              maxWidth: MediaQuery.of(context).size.width * 0.76),
          decoration: BoxDecoration(
            color: fromMe
                ? Reactor.arc.withValues(alpha: 0.14)
                : A.panelHi.withValues(alpha: 0.9),
            borderRadius: BorderRadius.circular(14),
            border: Border.all(
                color: fromMe
                    ? Reactor.arc.withValues(alpha: 0.35)
                    : A.line),
          ),
          child: Text(text,
              style: TextStyle(
                  color: fromMe ? A.text : A.text,
                  fontSize: 14.5,
                  height: 1.3)),
        ),
      );

  Widget _reactorRow(String live) => Container(
        padding: const EdgeInsets.fromLTRB(14, 8, 14, 14),
        decoration: const BoxDecoration(
          border: Border(top: BorderSide(color: A.line)),
        ),
        child: Row(children: [
          SizedBox(width: 60, height: 60, child: _reactor(60)),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisSize: MainAxisSize.min,
              children: [
                Row(children: [
                  _dot(_accent),
                  const SizedBox(width: 7),
                  Text(_label,
                      style: TextStyle(
                          color: _accent,
                          fontFamily: A.mono,
                          fontSize: 11,
                          letterSpacing: 2.2,
                          fontWeight: FontWeight.w700)),
                ]),
                if (live.isNotEmpty) ...[
                  const SizedBox(height: 5),
                  Text(live,
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                      style: const TextStyle(
                          color: A.text, fontSize: 15, height: 1.25)),
                ] else ...[
                  const SizedBox(height: 5),
                  const Text('“bye” bolo to band',
                      style: TextStyle(color: A.faint, fontSize: 11.5)),
                ],
              ],
            ),
          ),
          const SizedBox(width: 10),
          _stopBtn(46),
        ]),
      );

  // ── app-open / assist: the full cinematic ignition HUD ──────────────
  Widget _buildCinematic(BuildContext context) {
    final showReply = widget.state == AssistantUiState.speaking &&
        widget.replyText.isNotEmpty;
    return Positioned.fill(
      child: BackdropFilter(
        filter: ui.ImageFilter.blur(sigmaX: 22, sigmaY: 22),
        child: Container(
          color: A.deck.withValues(alpha: 0.86),
          child: SafeArea(
            child: Column(
              children: [
                _statusBar(),
                const Spacer(),
                SizedBox(width: 300, height: 300, child: _reactor(300)),
                const SizedBox(height: 6),
                AnimatedBuilder(
                  animation: _ign,
                  builder: (_, __) => Opacity(
                    opacity: (_ign.value - 0.6).clamp(0.0, 0.4) / 0.4,
                    child: const Text('AERIS',
                        style: TextStyle(
                            color: A.text,
                            fontSize: 30,
                            fontWeight: FontWeight.w800,
                            letterSpacing: 12)),
                  ),
                ),
                const SizedBox(height: 20),
                Row(mainAxisAlignment: MainAxisAlignment.center, children: [
                  _dot(_accent),
                  const SizedBox(width: 8),
                  Text(_label,
                      style: TextStyle(
                          color: _accent,
                          fontFamily: A.mono,
                          fontSize: 13,
                          letterSpacing: 3,
                          fontWeight: FontWeight.w700)),
                ]),
                const SizedBox(height: 16),
                Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 36),
                  child: Text(
                    showReply ? widget.replyText : widget.userText,
                    textAlign: TextAlign.center,
                    style: TextStyle(
                        color: showReply ? A.text : A.muted,
                        fontSize: showReply ? 18 : 20,
                        height: 1.35,
                        fontWeight: FontWeight.w600),
                  ),
                ),
                const Spacer(),
                _stopBtn(62),
                const SizedBox(height: 10),
                const Text('“bas” bolo ya tap karke band karo',
                    style: TextStyle(
                        color: A.faint, fontSize: 12, fontFamily: A.mono)),
                const SizedBox(height: 20),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _statusBar() => Padding(
        padding: const EdgeInsets.fromLTRB(20, 16, 8, 0),
        child: Row(children: [
          const Text('AERIS',
              style: TextStyle(
                  color: A.text,
                  fontFamily: A.mono,
                  fontSize: 15,
                  letterSpacing: 4,
                  fontWeight: FontWeight.w700)),
          const SizedBox(width: 10),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(6),
              border: Border.all(
                  color: (widget.online ? Reactor.mint : A.faint)
                      .withValues(alpha: 0.6)),
            ),
            child: Text(widget.online ? 'LAPTOP LINKED' : 'STANDALONE',
                style: TextStyle(
                    color: widget.online ? Reactor.mint : A.faint,
                    fontFamily: A.mono,
                    fontSize: 9,
                    letterSpacing: 1.5)),
          ),
          const Spacer(),
          IconButton(
              onPressed: widget.onStop,
              icon: const Icon(Icons.close_rounded, color: A.muted)),
        ]),
      );

  Widget _dot(Color c) => Container(
      width: 7,
      height: 7,
      decoration: BoxDecoration(shape: BoxShape.circle, color: c));

  Widget _stopBtn(double d) => GestureDetector(
        onTap: widget.onStop,
        child: Container(
          width: d,
          height: d,
          decoration: BoxDecoration(
            shape: BoxShape.circle,
            color: A.hot.withValues(alpha: 0.14),
            border: Border.all(color: A.hot.withValues(alpha: 0.7), width: 1.6),
          ),
          child: Icon(Icons.stop_rounded, color: A.hot, size: d * 0.48),
        ),
      );
}

class _ReactorPaint extends CustomPainter {
  final double t, ign, amp;
  final Color accent;
  _ReactorPaint(
      {required this.t,
      required this.ign,
      required this.amp,
      required this.accent});

  @override
  void paint(Canvas canvas, Size size) =>
      Reactor.paint(canvas, size, t: t, ignition: ign, amp: amp, accent: accent);

  @override
  bool shouldRepaint(_ReactorPaint old) =>
      old.t != t || old.ign != ign || old.amp != amp || old.accent != accent;
}
