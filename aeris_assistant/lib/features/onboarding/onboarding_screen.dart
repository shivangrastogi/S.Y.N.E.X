import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:permission_handler/permission_handler.dart';

import '../../app/scope.dart';
import '../../core/models.dart';
import '../../ui/kit/controls.dart';
import '../../ui/kit/surfaces.dart';
import '../../ui/reactor/reactor.dart';
import '../../ui/tokens.dart';

/// Three steps: hello → you → permissions. No fake progress, no jargon.
class OnboardingScreen extends StatefulWidget {
  const OnboardingScreen({super.key});

  @override
  State<OnboardingScreen> createState() => _OnboardingScreenState();
}

class _OnboardingScreenState extends State<OnboardingScreen> {
  final _pages = PageController();
  int _step = 0;
  final _name = TextEditingController();
  Lang _lang = Lang.hinglish;
  PermissionStatus? _mic, _contacts;

  @override
  void initState() {
    super.initState();
    _refreshPerms();
  }

  Future<void> _refreshPerms() async {
    final m = await Permission.microphone.status;
    final c = await Permission.contacts.status;
    if (mounted) {
      setState(() {
        _mic = m;
        _contacts = c;
      });
    }
  }

  void _next() {
    FocusScope.of(context).unfocus();
    if (_step == 2) return _finish();
    setState(() => _step++);
    _pages.animateToPage(_step, duration: M.slow, curve: M.ease);
  }

  void _back() {
    if (_step == 0) return;
    setState(() => _step--);
    _pages.animateToPage(_step, duration: M.slow, curve: M.ease);
  }

  void _finish() {
    final store = context.store;
    store.updateSettings(store.settings.copyWith(name: _name.text.trim(), lang: _lang, onboarded: true));
  }

  @override
  void dispose() {
    _pages.dispose();
    _name.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: HudBackground(
        child: SafeArea(
          child: Column(children: [
            Padding(
              padding: const EdgeInsets.fromLTRB(S.side, S.lg, S.side, 0),
              child: Row(children: [
                for (var i = 0; i < 3; i++) ...[
                  Expanded(
                    child: AnimatedContainer(
                      duration: M.base,
                      height: 2,
                      color: i <= _step ? C.cyan : C.hairline,
                    ),
                  ),
                  if (i < 2) const SizedBox(width: 6),
                ],
              ]),
            ),
            Expanded(
              child: PageView(
                controller: _pages,
                physics: const NeverScrollableScrollPhysics(),
                children: [_welcome(), _you(), _perms()],
              ),
            ),
            Padding(
              padding: const EdgeInsets.fromLTRB(S.side, 0, S.side, S.xl),
              child: Row(children: [
                if (_step > 0)
                  TextButton(
                    onPressed: _back,
                    child: Text('Back', style: T.body.copyWith(color: C.text2)),
                  ),
                const Spacer(),
                HudButton(
                  label: switch (_step) { 0 => 'Get started', 1 => 'Continue', _ => 'Start using AERIS' },
                  icon: _step == 2 ? null : Icons.arrow_forward_rounded,
                  onPressed: _next,
                ),
              ]),
            ),
          ]),
        ),
      ),
    );
  }

  Widget _welcome() {
    final w = MediaQuery.sizeOf(context).width;
    return ListView(
      padding: const EdgeInsets.symmetric(horizontal: S.side),
      children: [
        const SizedBox(height: S.xxl),
        Center(child: ReactorCore(state: CoreState.idle, size: (w * 0.55).clamp(180.0, 240.0))),
        const SizedBox(height: S.xxl),
        const Text('Hi, I\'m AERIS.', style: T.title),
        const SizedBox(height: S.sm),
        const Text(
          'A voice assistant that lives on your phone. Talk to me in Hinglish or English — I\'ll set alarms, call people, message them, open apps and remember things for you.',
          style: T.bodyDim,
        ),
        const SizedBox(height: S.xl),
        for (final (i, f) in const [
          (Icons.translate_rounded, 'Understands how you actually talk'),
          (Icons.phonelink_lock_outlined, 'Runs on this phone — your memory never leaves it'),
          (Icons.verified_user_outlined, 'Always asks before sending anything'),
        ].indexed)
          Padding(
            padding: const EdgeInsets.only(bottom: S.md),
            child: Row(children: [
              Icon(f.$1, size: 20, color: C.cyan),
              const SizedBox(width: S.md),
              Expanded(child: Text(f.$2, style: T.body.copyWith(fontSize: 14))),
            ]),
          ).animate(delay: M.stagger * (i + 4)).fadeIn(duration: M.slow).moveY(begin: 8, end: 0, curve: M.ease),
      ],
    );
  }

  Widget _you() {
    return ListView(
      padding: const EdgeInsets.symmetric(horizontal: S.side),
      children: [
        const SizedBox(height: S.huge),
        const Text('What should I call you?', style: T.title),
        const SizedBox(height: S.lg),
        Panel(
          padding: const EdgeInsets.symmetric(horizontal: S.lg, vertical: S.md),
          child: TextField(
            controller: _name,
            textCapitalization: TextCapitalization.words,
            style: T.body,
            decoration: const InputDecoration(hintText: 'Your name'),
          ),
        ),
        const SizedBox(height: S.huge),
        const Text('How should I talk?', style: T.title),
        const SizedBox(height: S.xs),
        const Text('You can change this any time in Settings.', style: T.bodyDim),
        const SizedBox(height: S.lg),
        for (final (l, title, sub) in const [
          (Lang.hinglish, 'Hinglish', 'Hindi + English, the way you actually talk'),
          (Lang.englishIn, 'English (India)', 'Indian English, no Hindi'),
          (Lang.englishUs, 'English (US)', 'American English'),
        ])
          Padding(
            padding: const EdgeInsets.only(bottom: S.sm),
            child: Panel(
              onTap: () => setState(() => _lang = l),
              borderColor: _lang == l ? C.cyan.withValues(alpha: 0.7) : C.hairline,
              fill: _lang == l ? C.cyan.withValues(alpha: 0.06) : C.surface,
              child: Row(children: [
                Expanded(
                  child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                    Row(children: [
                      Text(title, style: T.body.copyWith(fontWeight: FontWeight.w500)),
                      if (l == Lang.hinglish) ...[const SizedBox(width: S.sm), const Tag('Recommended', color: C.cyan)],
                    ]),
                    const SizedBox(height: 2),
                    Text(sub, style: T.small),
                  ]),
                ),
                AnimatedContainer(
                  duration: M.fast,
                  width: 18,
                  height: 18,
                  decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    border: Border.all(color: _lang == l ? C.cyan : C.text3, width: 1.5),
                  ),
                  padding: const EdgeInsets.all(3),
                  child: _lang == l ? const DecoratedBox(decoration: BoxDecoration(shape: BoxShape.circle, color: C.cyan)) : null,
                ),
              ]),
            ),
          ),
      ],
    );
  }

  Widget _perms() {
    Widget row(IconData icon, String title, String why, PermissionStatus? st, Permission p, {bool optional = false}) {
      final granted = st?.isGranted ?? false;
      return Padding(
        padding: const EdgeInsets.only(bottom: S.sm),
        child: Panel(
          child: Row(children: [
            Icon(icon, color: C.cyan, size: 22),
            const SizedBox(width: S.md + 2),
            Expanded(
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Row(children: [
                  Text(title, style: T.body.copyWith(fontWeight: FontWeight.w500)),
                  if (optional) ...[const SizedBox(width: S.sm), const Tag('Optional')],
                ]),
                const SizedBox(height: 2),
                Text(why, style: T.small),
              ]),
            ),
            const SizedBox(width: S.sm),
            granted
                ? const Row(mainAxisSize: MainAxisSize.min, children: [
                    Icon(Icons.check_rounded, color: C.mint, size: 18),
                    SizedBox(width: 4),
                    Text('Allowed', style: TextStyle(fontFamily: 'Sora', fontSize: 13, color: C.mint)),
                  ])
                : TextButton(
                    onPressed: () async {
                      final r = await p.request();
                      if (r.isPermanentlyDenied) await openAppSettings();
                      _refreshPerms();
                    },
                    child: Text('Allow', style: T.body.copyWith(color: C.cyan, fontWeight: FontWeight.w500)),
                  ),
          ]),
        ),
      );
    }

    return ListView(
      padding: const EdgeInsets.symmetric(horizontal: S.side),
      children: [
        const SizedBox(height: S.huge),
        const Text('Two permissions.', style: T.title),
        const SizedBox(height: S.xs),
        const Text('Each one unlocks something specific. Your voice never leaves this phone.', style: T.bodyDim),
        const SizedBox(height: S.xl),
        row(Icons.mic_none_rounded, 'Microphone', 'So I can hear you when you tap the core', _mic, Permission.microphone),
        row(Icons.people_outline_rounded, 'Contacts', 'To call or message people by name', _contacts, Permission.contacts,
            optional: true),
        const SizedBox(height: S.lg),
        const Panel(
          fill: Colors.transparent,
          child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Icon(Icons.info_outline_rounded, color: C.text3, size: 18),
            SizedBox(width: S.md),
            Expanded(
              child: Text(
                'AERIS listens and speaks with its own models, on this phone — no Google, no cloud. The always-on "Hey AERIS" wake word is coming in the next build; for now, tap the core.',
                style: T.small,
              ),
            ),
          ]),
        ),
      ],
    );
  }
}
