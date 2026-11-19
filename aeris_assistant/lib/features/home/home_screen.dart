import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:permission_handler/permission_handler.dart';

import '../../app/scope.dart';
import '../../brain/executor.dart';
import '../../core/models.dart';
import '../../ui/kit/controls.dart';
import '../../ui/kit/surfaces.dart';
import '../../ui/reactor/reactor.dart';
import '../../ui/tokens.dart';
import '../log/log_screen.dart';
import '../settings/settings_screen.dart';

/// One hero (the core), one line of text, the dock. Everything else lives
/// on its own tab (DESIGN R5).
class HomeScreen extends StatelessWidget {
  const HomeScreen({super.key, required this.onOpenLog});
  final VoidCallback onOpenLog;

  static String greeting(DateTime now) {
    final h = now.hour;
    if (h >= 5 && h < 12) return 'Good morning';
    if (h >= 12 && h < 17) return 'Good afternoon';
    if (h >= 17 && h < 22) return 'Good evening';
    return 'Up late';
  }

  @override
  Widget build(BuildContext context) {
    final store = context.store;
    final session = context.session;
    final size = MediaQuery.sizeOf(context);
    final core = (size.width * 0.74).clamp(220.0, 330.0);

    return SafeArea(
      bottom: false,
      child: ListenableBuilder(
        listenable: store,
        builder: (context, _) {
          final name = store.settings.name.trim();
          final last = store.activity.isEmpty ? null : store.activity.first;
          final hi = store.settings.lang == Lang.hinglish;
          return Column(children: [
            // top bar
            Padding(
              padding: const EdgeInsets.fromLTRB(S.side, S.md, S.sm, 0),
              child: Row(children: [
                Text('AERIS', style: T.wordmark),
                const SizedBox(width: S.md),
                const _MicStatus(),
                const Spacer(),
                IconBtn(Icons.tune_rounded,
                    tooltip: 'Settings',
                    onTap: () => Navigator.of(context).push(MaterialPageRoute(builder: (_) => const SettingsScreen()))),
              ]),
            ),

            // hero
            Expanded(
              child: Column(mainAxisAlignment: MainAxisAlignment.center, children: [
                Brackets(
                  arm: 14,
                  inset: 6,
                  color: C.cyan.withValues(alpha: 0.35),
                  child: ReactorCore(
                    state: CoreState.idle,
                    size: core,
                    onTap: () => session.start(),
                  ),
                ),
                const SizedBox(height: S.xl),
                Text(name.isEmpty ? greeting(DateTime.now()) : '${greeting(DateTime.now())}, $name', style: T.title)
                    .animate()
                    .fadeIn(duration: M.slow, delay: 120.ms)
                    .moveY(begin: 8, end: 0, curve: M.ease),
                const SizedBox(height: S.xs + 2),
                Text('Tap the core and speak.', style: T.bodyDim)
                    .animate()
                    .fadeIn(duration: M.slow, delay: 200.ms),
              ]),
            ),

            // suggestions
            SizedBox(
              height: 40,
              child: ListView(
                scrollDirection: Axis.horizontal,
                padding: const EdgeInsets.symmetric(horizontal: S.side),
                children: [
                  for (final (i, s) in (hi
                          ? const ['Kal subah 6:30 ka alarm', 'Battery kitni hai', '10 minute ka timer', 'Torch on']
                          : const ['Alarm at 6:30 am tomorrow', 'How much battery', '10 minute timer', 'Torch on'])
                      .indexed)
                    Padding(
                      padding: const EdgeInsets.only(right: S.sm),
                      child: _Chip(s, onTap: () => session.submitText(s)),
                    ).animate(delay: M.stagger * (i + 6)).fadeIn(duration: M.slow).moveX(begin: 12, end: 0, curve: M.ease),
                ],
              ),
            ),
            const SizedBox(height: S.md),

            // the last thing AERIS did (real, tappable)
            if (last != null)
              Padding(
                padding: const EdgeInsets.fromLTRB(S.side, 0, S.side, S.md),
                child: Panel(
                  onTap: onOpenLog,
                  padding: const EdgeInsets.symmetric(horizontal: S.lg, vertical: S.md),
                  child: Row(children: [
                    Icon(LogScreen.iconFor(last.tool), size: 18, color: last.status == TurnStatus.ok ? C.cyan : C.text3),
                    const SizedBox(width: S.md),
                    Expanded(
                      child: Text(last.reply,
                          maxLines: 1, overflow: TextOverflow.ellipsis, style: T.body.copyWith(fontSize: 14)),
                    ),
                    const SizedBox(width: S.sm),
                    Text(ago(last.at), style: T.mono.copyWith(fontSize: 11, color: C.text3)),
                  ]),
                ),
              ).animate().fadeIn(duration: M.slow, delay: 300.ms),

            const _Dock(),
          ]);
        },
      ),
    );
  }
}

String ago(DateTime t) {
  final d = DateTime.now().difference(t);
  if (d.inSeconds < 60) return 'now';
  if (d.inMinutes < 60) return '${d.inMinutes}m';
  if (d.inHours < 24) return '${d.inHours}h';
  return '${d.inDays}d';
}

class _Chip extends StatelessWidget {
  const _Chip(this.text, {required this.onTap});
  final String text;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) => Material(
        color: C.surface.withValues(alpha: 0.7),
        shape: const ChamferBorder(cut: 5),
        clipBehavior: Clip.antiAlias,
        child: InkWell(
          onTap: () {
            HapticFeedback.selectionClick();
            onTap();
          },
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 14),
            child: Center(child: Text(text, style: T.small.copyWith(color: C.text1, fontSize: 13))),
          ),
        ),
      );
}

/// Text field + the mic. The mic is the only round thing besides the core.
class _Dock extends StatefulWidget {
  const _Dock();

  @override
  State<_Dock> createState() => _DockState();
}

class _DockState extends State<_Dock> {
  final _c = TextEditingController();
  final _focus = FocusNode();

  @override
  void initState() {
    super.initState();
    _c.addListener(() => setState(() {}));
  }

  @override
  void dispose() {
    _c.dispose();
    _focus.dispose();
    super.dispose();
  }

  void _send() {
    final t = _c.text.trim();
    if (t.isEmpty) return;
    _c.clear();
    _focus.unfocus();
    context.session.submitText(t);
  }

  @override
  Widget build(BuildContext context) {
    final hasText = _c.text.trim().isNotEmpty;
    return Padding(
      padding: const EdgeInsets.fromLTRB(S.side, 0, S.side, S.md),
      child: Row(children: [
        Expanded(
          child: Panel(
            padding: const EdgeInsets.only(left: S.lg, right: S.xs),
            child: Row(children: [
              Expanded(
                child: TextField(
                  controller: _c,
                  focusNode: _focus,
                  style: T.body.copyWith(fontSize: 14.5),
                  textInputAction: TextInputAction.send,
                  onSubmitted: (_) => _send(),
                  decoration: const InputDecoration(
                    hintText: 'Type a command',
                    contentPadding: EdgeInsets.symmetric(vertical: 16),
                  ),
                ),
              ),
              AnimatedOpacity(
                opacity: hasText ? 1 : 0,
                duration: M.fast,
                child: IconBtn(Icons.arrow_upward_rounded, color: C.cyan, onTap: hasText ? _send : () {}),
              ),
            ]),
          ),
        ),
        const SizedBox(width: S.md),
        _MicButton(onTap: () {
          _focus.unfocus();
          context.session.start();
        }),
      ]),
    ).animate().fadeIn(duration: M.slow, delay: 250.ms).moveY(begin: 10, end: 0, curve: M.ease);
  }
}

class _MicButton extends StatelessWidget {
  const _MicButton({required this.onTap});
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) => Semantics(
        button: true,
        label: 'Talk to AERIS',
        child: GestureDetector(
          onTap: onTap,
          child: Container(
            width: 54,
            height: 54,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              color: C.cyan.withValues(alpha: 0.10),
              border: Border.all(color: C.cyan.withValues(alpha: 0.8), width: 1.2),
              boxShadow: [BoxShadow(color: C.cyan.withValues(alpha: 0.25), blurRadius: 18)],
            ),
            child: const Icon(Icons.mic_none_rounded, color: C.cyanHot, size: 24),
          ),
        ),
      );
}

/// Real status (DESIGN R1): mint "Ready" only when the mic is allowed.
class _MicStatus extends StatefulWidget {
  const _MicStatus();

  @override
  State<_MicStatus> createState() => _MicStatusState();
}

class _MicStatusState extends State<_MicStatus> with WidgetsBindingObserver {
  bool? _ok;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    _check();
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState s) {
    if (s == AppLifecycleState.resumed) _check();
  }

  Future<void> _check() async {
    bool ok;
    try {
      ok = await Permission.microphone.isGranted;
    } catch (_) {
      ok = false;
    }
    if (mounted) setState(() => _ok = ok);
  }

  @override
  Widget build(BuildContext context) {
    if (_ok == null) return const SizedBox.shrink();
    return GestureDetector(
      onTap: _ok! ? null : () async {
        final r = await Permission.microphone.request();
        if (r.isPermanentlyDenied) await openAppSettings();
        _check();
      },
      child: Row(mainAxisSize: MainAxisSize.min, children: [
        StatusDot(size: 6, color: _ok! ? C.mint : C.amber, pulse: _ok!),
        const SizedBox(width: 6),
        Text(_ok! ? 'Ready' : 'Mic off — tap to allow', style: T.small.copyWith(color: _ok! ? C.text2 : C.amber)),
      ]),
    );
  }
}

/// Exported for Log/other screens that need the label.
String labelFor(String tool) => toolLabel(tool);
