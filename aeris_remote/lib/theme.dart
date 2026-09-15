import 'dart:math' as math;
import 'package:flutter/material.dart';

/// AERIS Command Deck — design tokens + the signature presence orb.
///
/// The whole app is a restrained graphite console; the one living element is
/// the plasma orb (the assistant's "face" + connection status). Data that is
/// actually true — transport, timestamps, keys — is set in monospace, like a
/// real terminal. Everything else stays quiet.
class A {
  // Surfaces (blue-black graphite, never pure #000).
  static const deck = Color(0xFF0A0C11);
  static const panel = Color(0xFF12151D);
  static const panelHi = Color(0xFF191D27);
  static const line = Color(0xFF242A36);

  // Plasma signature — indigo → cyan → mint. Used sparingly.
  static const plasmaA = Color(0xFF7C6CFF);
  static const plasmaB = Color(0xFF37E0EA);
  static const plasmaC = Color(0xFF54F0C0);
  static const hot = Color(0xFFFF5A6E); // ring / stop / destructive

  // Ink.
  static const text = Color(0xFFECEFF6);
  static const muted = Color(0xFF8A93A6);
  static const faint = Color(0xFF565F70);

  static const plasma = LinearGradient(
    colors: [plasmaA, plasmaB, plasmaC],
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
  );

  static const mono = 'monospace';

  /// The small ALL-CAPS console label device (encodes section, not decoration).
  static Widget label(String s, {Color? color}) => Text(
        s.toUpperCase(),
        style: TextStyle(
          fontFamily: mono,
          fontSize: 10.5,
          letterSpacing: 1.8,
          fontWeight: FontWeight.w700,
          color: color ?? muted,
        ),
      );
}

/// The AERIS presence orb — a breathing plasma ring. Its state IS the assistant:
/// steady when online, a fast pulse when listening/live, a dim grey when offline.
/// Manages its own ticker so callers don't need one; respects reduced-motion.
class AerisOrb extends StatefulWidget {
  final double size;
  final bool online;
  final bool active; // listening / live → faster, brighter pulse

  const AerisOrb({
    super.key,
    this.size = 40,
    this.online = false,
    this.active = false,
  });

  @override
  State<AerisOrb> createState() => _AerisOrbState();
}

class _AerisOrbState extends State<AerisOrb>
    with SingleTickerProviderStateMixin {
  late final AnimationController _c;

  @override
  void initState() {
    super.initState();
    _c = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 2600),
    )..repeat(reverse: true);
    _sync();
  }

  void _sync() {
    _c.duration =
        Duration(milliseconds: widget.active ? 900 : 2600);
    if (widget.online || widget.active) {
      if (!_c.isAnimating) _c.repeat(reverse: true);
    } else {
      _c.stop();
      _c.value = 0.5;
    }
  }

  @override
  void didUpdateWidget(covariant AerisOrb old) {
    super.didUpdateWidget(old);
    if (old.online != widget.online || old.active != widget.active) _sync();
  }

  @override
  void dispose() {
    _c.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final reduce = MediaQuery.maybeOf(context)?.disableAnimations ?? false;
    return AnimatedBuilder(
      animation: _c,
      builder: (_, __) {
        final t = reduce ? 0.5 : _c.value;
        return CustomPaint(
          size: Size.square(widget.size),
          painter: _OrbPainter(
            t: t,
            online: widget.online,
            active: widget.active,
          ),
        );
      },
    );
  }
}

class _OrbPainter extends CustomPainter {
  final double t;
  final bool online;
  final bool active;
  _OrbPainter({required this.t, required this.online, required this.active});

  @override
  void paint(Canvas canvas, Size size) {
    final c = size.center(Offset.zero);
    final r = size.width / 2;
    final breathe = 0.90 + 0.10 * t; // 0.90..1.00
    final rot = t * 2 * math.pi;

    final live = online || active;
    final ringColors = live
        ? const [A.plasmaA, A.plasmaB, A.plasmaC, A.plasmaA]
        : const [A.faint, A.faint, A.faint, A.faint];

    // Outer glow — how "awake" the assistant looks.
    final glowOpacity = live ? (active ? 0.55 : 0.34) * (0.6 + 0.4 * t) : 0.0;
    if (glowOpacity > 0) {
      final glow = Paint()
        ..shader = RadialGradient(
          colors: [
            A.plasmaB.withValues(alpha: glowOpacity),
            A.plasmaA.withValues(alpha: 0.0),
          ],
        ).createShader(Rect.fromCircle(center: c, radius: r * 1.15));
      canvas.drawCircle(c, r * 1.15, glow);
    }

    // Gradient ring stroke — the plasma signature.
    final ringR = r * 0.80 * breathe;
    final ring = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = math.max(2.0, r * 0.14)
      ..strokeCap = StrokeCap.round
      ..shader = SweepGradient(
        colors: ringColors,
        transform: GradientRotation(rot),
      ).createShader(Rect.fromCircle(center: c, radius: ringR));
    canvas.drawCircle(c, ringR, ring);

    // Dark core with a faint plasma highlight, so it reads as a lens/eye.
    final core = Paint()
      ..shader = RadialGradient(
        colors: [
          (live ? A.plasmaB : A.faint).withValues(alpha: live ? 0.30 : 0.14),
          A.deck,
        ],
        stops: const [0.0, 1.0],
      ).createShader(Rect.fromCircle(center: c, radius: ringR * 0.72));
    canvas.drawCircle(c, ringR * 0.72, core);
  }

  @override
  bool shouldRepaint(covariant _OrbPainter o) =>
      o.t != t || o.online != online || o.active != active;
}
