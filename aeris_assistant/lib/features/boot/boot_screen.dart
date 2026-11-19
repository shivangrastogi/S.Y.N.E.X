import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';

import '../../ui/kit/surfaces.dart';
import '../../ui/reactor/reactor.dart';
import '../../ui/tokens.dart';

/// Ignition. The core draws itself in, then the wordmark resolves.
/// Long version on first run, short on every launch after (no fake boot log).
class BootScreen extends StatefulWidget {
  const BootScreen({super.key, required this.firstRun, required this.onDone});
  final bool firstRun;
  final VoidCallback onDone;

  @override
  State<BootScreen> createState() => _BootScreenState();
}

class _BootScreenState extends State<BootScreen> with SingleTickerProviderStateMixin {
  late final AnimationController _c = AnimationController(
    vsync: this,
    duration: Duration(milliseconds: widget.firstRun ? 2100 : 1100),
  );

  @override
  void initState() {
    super.initState();
    _c.forward().whenComplete(() {
      if (mounted) widget.onDone();
    });
  }

  @override
  void dispose() {
    _c.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final w = MediaQuery.sizeOf(context).width;
    return Scaffold(
      body: HudBackground(
        hazeAt: const Alignment(0, -0.1),
        child: Center(
          child: Column(mainAxisSize: MainAxisSize.min, children: [
            AnimatedBuilder(
              animation: _c,
              builder: (_, _) => ReactorCore(
                state: CoreState.idle,
                ignition: Curves.easeInOut.transform((_c.value / 0.85).clamp(0.0, 1.0)),
                size: (w * 0.62).clamp(200.0, 280.0),
              ),
            ),
            const SizedBox(height: S.xxl),
            Text('AERIS', style: T.display)
                .animate(delay: Duration(milliseconds: widget.firstRun ? 900 : 350))
                .fadeIn(duration: M.slow)
                .custom(
                  duration: 600.ms,
                  builder: (_, v, child) => ShaderMask(
                    shaderCallback: (r) => LinearGradient(
                      colors: [C.text1, C.text1, C.text1.withValues(alpha: 0)],
                      stops: [0, v, (v + 0.15).clamp(0, 1)],
                    ).createShader(r),
                    child: child,
                  ),
                ),
            const SizedBox(height: S.lg),
            AnimatedBuilder(
              animation: _c,
              builder: (_, _) => Container(
                width: 96,
                height: 1.5,
                alignment: Alignment.centerLeft,
                color: C.hairline,
                child: FractionallySizedBox(
                  widthFactor: _c.value,
                  child: Container(
                    decoration: BoxDecoration(
                      color: C.cyan,
                      boxShadow: [BoxShadow(color: C.cyan.withValues(alpha: 0.6), blurRadius: 6)],
                    ),
                  ),
                ),
              ),
            ),
          ]),
        ),
      ),
    );
  }
}
