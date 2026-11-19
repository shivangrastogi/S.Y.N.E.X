import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:permission_handler/permission_handler.dart';

import '../../app/scope.dart';
import '../../core/models.dart';
import '../../ui/kit/controls.dart';
import '../../ui/kit/surfaces.dart';
import '../../ui/reactor/reactor.dart';
import '../../ui/tokens.dart';
import '../../voice/session.dart';

/// Full-screen voice. The core is the hero; text below it changes with the
/// phase. Opaque background — no blur under anything that animates.
class VoiceOverlay extends StatelessWidget {
  const VoiceOverlay({super.key});

  @override
  Widget build(BuildContext context) {
    final session = context.session;
    final hi = context.store.settings.lang == Lang.hinglish;
    final w = MediaQuery.sizeOf(context).width;

    return Material(
      color: C.bg,
      child: HudBackground(
        hazeAt: const Alignment(0, -0.42),
        child: SafeArea(
          child: ListenableBuilder(
            listenable: session,
            builder: (context, _) {
              final p = session.phase;
              final (word, dot) = switch (p) {
                Phase.listening => ('LISTENING', C.cyan),
                Phase.processing => ('THINKING', C.cyan),
                Phase.speaking => ('SPEAKING', C.cyan),
                Phase.approval => ('NEEDS YOUR OK', C.amber),
                Phase.noSignal => ('NO SPEECH', C.text3),
                Phase.error => ('MIC UNAVAILABLE', C.red),
                Phase.idle => ('DONE', C.mint),
              };
              return Column(children: [
                Padding(
                  padding: const EdgeInsets.fromLTRB(S.side, S.md, S.sm, 0),
                  child: Row(children: [
                    StatusDot(color: dot, size: 7),
                    const SizedBox(width: S.md),
                    DecodeText(word, style: T.stateWord.copyWith(color: dot == C.text3 ? C.text2 : dot)),
                    const Spacer(),
                    IconBtn(Icons.close_rounded, tooltip: 'Close', onTap: session.stop),
                  ]),
                ),
                Expanded(
                  flex: 11,
                  child: Center(
                    child: ReactorCore(
                      state: session.coreState,
                      level: session.level,
                      beat: session.beat,
                      size: (w * 0.80).clamp(240.0, 360.0),
                      onTap: () {
                        if (p == Phase.speaking || p == Phase.idle || p == Phase.noSignal) {
                          session.start(); // barge in / talk again
                        }
                      },
                    ),
                  ),
                ),
                Expanded(
                  flex: 10,
                  child: AnimatedSwitcher(
                    duration: M.base,
                    switchInCurve: M.ease,
                    transitionBuilder: (c, a) => FadeTransition(
                      opacity: a,
                      child: SlideTransition(
                        position: Tween(begin: const Offset(0, 0.04), end: Offset.zero).animate(a),
                        child: c,
                      ),
                    ),
                    child: KeyedSubtree(
                      key: ValueKey(p == Phase.speaking || p == Phase.idle ? 'reply' : p.name),
                      child: _body(context, session, hi),
                    ),
                  ),
                ),
                _footer(context, session, hi),
              ]);
            },
          ),
        ),
      ),
    );
  }

  Widget _body(BuildContext context, VoiceSession s, bool hi) {
    final lastUser = s.lines.lastWhere((l) => l.fromUser, orElse: () => const Line(true, '')).text;
    switch (s.phase) {
      case Phase.listening:
        return _Pad(
          child: s.partial.isEmpty
              ? Text(
                  hi ? 'Boliye… jaise "kal subah 6 baje ka alarm laga do"' : 'Go ahead… like "set an alarm for 6 am tomorrow"',
                  style: T.transcript.copyWith(color: C.text3, fontSize: 19),
                )
              : _Typing(s.partial),
        );
      case Phase.processing:
        return _Pad(child: Text(s.notice ?? lastUser, style: T.transcript.copyWith(color: C.text2)));
      case Phase.approval:
        final a = s.approval!;
        return _Pad(
          child: Brackets(
            color: C.amber,
            child: Panel(
              borderColor: C.amber.withValues(alpha: 0.45),
              fill: C.amber.withValues(alpha: 0.05),
              padding: const EdgeInsets.all(S.lg + 2),
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, mainAxisSize: MainAxisSize.min, children: [
                Text(a.title, style: T.heading),
                if (a.to != null) ...[
                  const SizedBox(height: S.md),
                  Text('TO', style: T.label),
                  const SizedBox(height: 2),
                  Text(a.to!, style: T.body.copyWith(fontWeight: FontWeight.w500)),
                ],
                if (a.body != null) ...[
                  const SizedBox(height: S.md),
                  Text(a.to != null ? 'MESSAGE' : 'SEARCH FOR', style: T.label),
                  const SizedBox(height: 2),
                  Text('“${a.body}”', style: T.body),
                ],
                const SizedBox(height: S.lg),
                Row(children: [
                  Expanded(
                    child: HudButton(
                        label: a.to != null ? 'Send' : 'Search',
                        kind: BtnKind.approve,
                        expand: true,
                        onPressed: s.approve),
                  ),
                  const SizedBox(width: S.md),
                  Expanded(child: HudButton(label: 'Cancel', kind: BtnKind.outline, expand: true, onPressed: s.deny)),
                ]),
                const SizedBox(height: S.md),
                Center(child: Text(hi ? 'ya boliye "haan" / "nahi"' : 'or say "yes" / "no"', style: T.small)),
              ]),
            ),
          ),
        );
      case Phase.noSignal:
        return _Pad(
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text(hi ? 'Kuch sunai nahi diya.' : 'I didn\'t catch that.', style: T.title),
            const SizedBox(height: S.sm),
            Text(hi ? 'Phir se boliye, ya type kar dijiye.' : 'Try again, or type instead.', style: T.bodyDim),
            const SizedBox(height: S.xl),
            HudButton(label: hi ? 'Phir se suno' : 'Try again', icon: Icons.mic_none_rounded, onPressed: s.retry),
          ]),
        );
      case Phase.error:
        return _Pad(
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text(s.error ?? 'Something went wrong.', style: T.body),
            const SizedBox(height: S.xl),
            Row(children: [
              HudButton(label: 'Open settings', kind: BtnKind.outline, onPressed: () => openAppSettings()),
              const SizedBox(width: S.md),
              HudButton(label: 'Try again', onPressed: s.retry),
            ]),
          ]),
        );
      case Phase.speaking:
      case Phase.idle:
        return _Pad(
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            if (lastUser.isNotEmpty) ...[
              Text(lastUser, style: T.bodyDim, maxLines: 2, overflow: TextOverflow.ellipsis),
              const SizedBox(height: S.md),
            ],
            _SpokenReply(s),
            if (s.replyDetail != null && s.replyDetail!.isNotEmpty) ...[
              const SizedBox(height: S.md),
              Text(s.replyDetail!, style: T.mono.copyWith(color: C.text2)),
            ],
          ]),
        );
    }
  }

  Widget _footer(BuildContext context, VoiceSession s, bool hi) {
    final talking = s.phase == Phase.listening || s.phase == Phase.speaking || s.phase == Phase.processing;
    return Padding(
      padding: const EdgeInsets.fromLTRB(S.side, 0, S.side, S.lg),
      child: SizedBox(
        height: 64,
        child: AnimatedSwitcher(
          duration: M.base,
          child: talking
              ? Row(key: const ValueKey('talk'), mainAxisAlignment: MainAxisAlignment.center, children: [
                  _EndButton(onTap: s.stop),
                  const SizedBox(width: S.lg),
                  Text(hi ? 'Khatam karne ke liye "bas" boliye' : 'Say "bye" to end', style: T.small),
                ])
              : s.phase == Phase.idle
                  ? Row(key: const ValueKey('done'), mainAxisAlignment: MainAxisAlignment.center, children: [
                      HudButton(label: hi ? 'Aur kuch' : 'Ask again', icon: Icons.mic_none_rounded, onPressed: s.start),
                      const SizedBox(width: S.md),
                      HudButton(label: 'Close', kind: BtnKind.outline, onPressed: s.stop),
                    ])
                  : const SizedBox.shrink(),
        ),
      ),
    );
  }
}

class _Pad extends StatelessWidget {
  const _Pad({required this.child});
  final Widget child;

  @override
  Widget build(BuildContext context) => Align(
        alignment: Alignment.topLeft,
        child: SingleChildScrollView(
          padding: const EdgeInsets.symmetric(horizontal: S.side + 4, vertical: S.sm),
          child: child,
        ),
      );
}

/// Live transcript with a blinking block cursor.
class _Typing extends StatelessWidget {
  const _Typing(this.text);
  final String text;

  @override
  Widget build(BuildContext context) => Text.rich(TextSpan(children: [
        TextSpan(text: text, style: T.transcript),
        WidgetSpan(
          alignment: PlaceholderAlignment.middle,
          child: Container(width: 9, height: 22, margin: const EdgeInsets.only(left: 4), color: C.cyan)
              .animate(onPlay: (c) => c.repeat(reverse: true))
              .fade(begin: 1, end: 0.1, duration: 520.ms),
        ),
      ]));
}

/// The reply, lit word by word as it's spoken: spoken = bright, current =
/// cyan, upcoming = dim. Falls back to full text when the engine has no
/// word timing.
class _SpokenReply extends StatelessWidget {
  const _SpokenReply(this.s);
  final VoiceSession s;

  @override
  Widget build(BuildContext context) {
    final failed = s.lines.isNotEmpty && !s.lines.last.fromUser && s.lines.last.failed;
    final base = T.transcript.copyWith(color: failed ? C.amber : C.text1);
    return ValueListenableBuilder<(int, int)?>(
      valueListenable: s.spokenRange,
      builder: (_, r, _) {
        final text = s.reply;
        if (r == null || s.phase != Phase.speaking || r.$2 > text.length || r.$1 >= r.$2) {
          return Text(text, style: base);
        }
        return Text.rich(TextSpan(children: [
          TextSpan(text: text.substring(0, r.$1), style: base),
          TextSpan(
              text: text.substring(r.$1, r.$2),
              style: base.copyWith(color: C.cyanHot, shadows: [Shadow(color: C.cyan.withValues(alpha: 0.7), blurRadius: 12)])),
          TextSpan(text: text.substring(r.$2), style: base.copyWith(color: C.text3)),
        ]));
      },
    );
  }
}

class _EndButton extends StatelessWidget {
  const _EndButton({required this.onTap});
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) => Semantics(
        button: true,
        label: 'End conversation',
        child: GestureDetector(
          onTap: onTap,
          child: Container(
            width: 52,
            height: 52,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              border: Border.all(color: C.red.withValues(alpha: 0.75), width: 1.2),
              color: C.red.withValues(alpha: 0.08),
            ),
            child: Center(child: Container(width: 14, height: 14, color: C.red)),
          ),
        ),
      );
}
