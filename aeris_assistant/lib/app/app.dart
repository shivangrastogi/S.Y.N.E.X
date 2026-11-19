import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_animate/flutter_animate.dart';

import '../features/boot/boot_screen.dart';
import '../features/home/home_screen.dart';
import '../features/log/log_screen.dart';
import '../features/memory/memory_screen.dart';
import '../features/onboarding/onboarding_screen.dart';
import '../features/protocols/protocols_screen.dart';
import '../features/voice/voice_overlay.dart';
import '../ui/kit/surfaces.dart';
import '../ui/tokens.dart';
import 'scope.dart';

/// Boot → onboarding (first run) → shell.
class RootGate extends StatefulWidget {
  const RootGate({super.key});

  @override
  State<RootGate> createState() => _RootGateState();
}

class _RootGateState extends State<RootGate> {
  bool _booted = false;

  @override
  Widget build(BuildContext context) {
    final store = context.store;
    return ListenableBuilder(
      listenable: store,
      builder: (context, _) {
        final Widget child;
        if (!_booted) {
          child = BootScreen(
            key: const ValueKey('boot'),
            firstRun: !store.settings.onboarded,
            onDone: () => setState(() => _booted = true),
          );
        } else if (!store.settings.onboarded) {
          child = const OnboardingScreen(key: ValueKey('onb'));
        } else {
          child = const Shell(key: ValueKey('shell'));
        }
        return AnimatedSwitcher(
          duration: M.slow,
          switchInCurve: M.ease,
          child: child,
        );
      },
    );
  }
}

class Shell extends StatefulWidget {
  const Shell({super.key});

  @override
  State<Shell> createState() => _ShellState();
}

class _ShellState extends State<Shell> {
  int _tab = 0;

  static const _tabs = [
    (Icons.blur_circular_outlined, 'Home'),
    (Icons.receipt_long_outlined, 'Log'),
    (Icons.bookmark_border_rounded, 'Memory'),
    (Icons.account_tree_outlined, 'Protocols'),
  ];

  void go(int i) {
    if (i == _tab) return;
    HapticFeedback.selectionClick();
    setState(() => _tab = i);
  }

  @override
  Widget build(BuildContext context) {
    final session = context.session;
    final pages = [
      HomeScreen(onOpenLog: () => go(1)),
      const LogScreen(),
      const MemoryScreen(),
      const ProtocolsScreen(),
    ];
    return ListenableBuilder(
      listenable: session,
      builder: (context, _) => PopScope(
        canPop: !session.active && _tab == 0,
        onPopInvokedWithResult: (didPop, _) {
          if (didPop) return;
          if (session.active) {
            session.stop();
          } else {
            go(0);
          }
        },
        child: Scaffold(
          resizeToAvoidBottomInset: true,
          body: Stack(children: [
            HudBackground(
              child: Column(children: [
                Expanded(
                  child: IndexedStack(
                    index: _tab,
                    children: [
                      for (var i = 0; i < pages.length; i++)
                        TickerMode(enabled: i == _tab && !session.active, child: pages[i]),
                    ],
                  ),
                ),
                _NavBar(tabs: _tabs, index: _tab, onTap: go),
              ]),
            ),
            AnimatedSwitcher(
              duration: M.base,
              child: session.active
                  ? const VoiceOverlay(key: ValueKey('voice'))
                  : const SizedBox.shrink(key: ValueKey('none')),
            ),
          ]),
        ),
      ),
    );
  }
}

class _NavBar extends StatelessWidget {
  const _NavBar({required this.tabs, required this.index, required this.onTap});
  final List<(IconData, String)> tabs;
  final int index;
  final ValueChanged<int> onTap;

  @override
  Widget build(BuildContext context) {
    final bottom = MediaQuery.paddingOf(context).bottom;
    return Container(
      decoration: const BoxDecoration(
        color: Color(0xF004070B),
        border: Border(top: BorderSide(color: C.hairlineSoft)),
      ),
      padding: EdgeInsets.only(bottom: bottom),
      child: Row(children: [
        for (var i = 0; i < tabs.length; i++)
          Expanded(
            child: InkWell(
              onTap: () => onTap(i),
              child: SizedBox(
                height: 62,
                child: Stack(alignment: Alignment.center, children: [
                  Positioned(
                    top: 0,
                    child: AnimatedContainer(
                      duration: M.base,
                      curve: M.ease,
                      width: i == index ? 22 : 0,
                      height: 2,
                      decoration: BoxDecoration(
                        color: C.cyan,
                        boxShadow: [BoxShadow(color: C.cyan.withValues(alpha: 0.6), blurRadius: 8)],
                      ),
                    ),
                  ),
                  Column(mainAxisSize: MainAxisSize.min, children: [
                    Icon(tabs[i].$1, size: 22, color: i == index ? C.cyan : C.text3),
                    const SizedBox(height: 4),
                    Text(tabs[i].$2,
                        style: T.small.copyWith(
                            fontSize: 11, color: i == index ? C.text1 : C.text3, height: 1)),
                  ]),
                ]),
              ),
            ),
          ),
      ]),
    ).animate().fadeIn(duration: M.slow);
  }
}
