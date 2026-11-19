import 'dart:math' as math;

import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter/scheduler.dart';

import '../tokens.dart';

/// What the core is doing. Maps 1:1 to the voice session (BUILD_GUIDE §7.6).
enum CoreState { idle, listening, processing, speaking, approval, success, error, offline }

/// The AERIS reactor core.
///
/// Performance contract (BUILD_GUIDE §12.7 — aeris_remote ANR lesson):
/// one [Ticker], no setState per frame, the painter repaints off a
/// [ChangeNotifier], everything wrapped in a [RepaintBoundary].
///
/// [level] = live energy 0..1 (mic level while listening).
/// [beat]  = notifies once per spoken word → a ripple + energy kick.
class ReactorCore extends StatefulWidget {
  const ReactorCore({
    super.key,
    required this.state,
    this.level,
    this.beat,
    this.ignition = 1,
    this.size = 280,
    this.onTap,
  });

  final CoreState state;
  final ValueListenable<double>? level;
  final Listenable? beat;
  final double ignition;
  final double size;
  final VoidCallback? onTap;

  @override
  State<ReactorCore> createState() => _ReactorCoreState();
}

class _ReactorCoreState extends State<ReactorCore> with SingleTickerProviderStateMixin {
  late final Ticker _ticker;
  final _frame = _Frame();
  Duration _last = Duration.zero;

  @override
  void initState() {
    super.initState();
    _frame.snapTo(widget.state);
    _ticker = createTicker(_tick)..start();
    widget.beat?.addListener(_onBeat);
  }

  @override
  void didUpdateWidget(covariant ReactorCore old) {
    super.didUpdateWidget(old);
    if (old.beat != widget.beat) {
      old.beat?.removeListener(_onBeat);
      widget.beat?.addListener(_onBeat);
    }
    if (old.state != widget.state) {
      switch (widget.state) {
        case CoreState.listening when old.state == CoreState.idle:
          _frame.flash(C.cyanHot);
        case CoreState.success:
          _frame.flash(C.mint);
        case CoreState.error:
          _frame.flash(C.red);
        case CoreState.approval:
          _frame.flash(C.amber);
        default:
          break;
      }
    }
  }

  void _onBeat() => _frame.beat();

  void _tick(Duration elapsed) {
    final dt = ((elapsed - _last).inMicroseconds / 1e6).clamp(0.0, 0.05);
    _last = elapsed;
    _frame.step(
      dt,
      widget.state,
      widget.level?.value ?? 0,
      widget.ignition,
      reduceMotion: MediaQuery.maybeDisableAnimationsOf(context) ?? false,
    );
  }

  @override
  void dispose() {
    widget.beat?.removeListener(_onBeat);
    _ticker.dispose();
    _frame.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return RepaintBoundary(
      child: GestureDetector(
        onTap: widget.onTap,
        behavior: HitTestBehavior.opaque,
        child: SizedBox.square(
          dimension: widget.size,
          child: CustomPaint(painter: _ReactorPainter(_frame)),
        ),
      ),
    );
  }
}

/// Per-state targets. The frame eases toward them so state changes glide.
class _Target {
  const _Target(this.glow, this.spectrum, this.spin, this.dim, this.tint, this.chase);
  final double glow, spectrum, spin, dim, chase;
  final Color tint;

  static _Target of(CoreState s) => switch (s) {
        CoreState.idle => const _Target(0.55, 0.12, 1.0, 1.0, C.cyan, 0),
        CoreState.listening => const _Target(0.80, 1.00, 1.7, 1.0, C.cyan, 0),
        CoreState.processing => const _Target(0.70, 0.15, 4.2, 1.0, C.cyan, 1),
        CoreState.speaking => const _Target(0.85, 0.70, 1.4, 1.0, C.cyan, 0),
        CoreState.approval => const _Target(0.60, 0.10, 0.6, 1.0, C.amber, 0),
        CoreState.success => const _Target(0.75, 0.10, 1.0, 1.0, C.mint, 0),
        CoreState.error => const _Target(0.50, 0.05, 0.5, 1.0, C.red, 0),
        CoreState.offline => const _Target(0.12, 0.00, 0.2, 0.45, C.cyanDim, 0),
      };
}

class _Frame extends ChangeNotifier {
  double t = 0;
  double glow = 0.55, spectrum = 0.1, spin = 1, dim = 1, chase = 0;
  Color tint = C.cyan;
  double energy = 0; // smoothed live energy
  double beatEnergy = 0; // decays after each spoken word
  double phaseA = 0, phaseB = 0, chaseHead = 0;
  double ignition = 1;
  bool reduce = false;
  final List<double> ripples = [];
  double flashAge = -1;
  Color flashColor = C.cyanHot;

  static const rippleLife = 1.15;
  static const flashLife = 0.55;

  void snapTo(CoreState s) {
    final g = _Target.of(s);
    glow = g.glow;
    spectrum = g.spectrum;
    spin = g.spin;
    dim = g.dim;
    tint = g.tint;
    chase = g.chase;
  }

  void beat() {
    beatEnergy = 1;
    if (!reduce && ripples.length < 4) ripples.add(0);
  }

  void flash(Color c) {
    flashColor = c;
    flashAge = 0;
  }

  void step(double dt, CoreState s, double level, double ign, {required bool reduceMotion}) {
    reduce = reduceMotion;
    t += dt;
    ignition = ign;
    final g = _Target.of(s);
    final k = 1 - math.exp(-dt * 6); // ~6/s easing
    glow += (g.glow - glow) * k;
    spectrum += (g.spectrum - spectrum) * k;
    spin += (g.spin - spin) * k;
    dim += (g.dim - dim) * k;
    chase += (g.chase - chase) * k;
    tint = Color.lerp(tint, g.tint, k)!;

    beatEnergy *= math.exp(-dt * 4.5);
    final raw = switch (s) {
      CoreState.listening => level,
      CoreState.speaking => 0.25 + 0.75 * beatEnergy,
      _ => 0.0,
    };
    final ke = 1 - math.exp(-dt * (raw > energy ? 18 : 7)); // fast attack, slow release
    energy += (raw - energy) * ke;

    final motion = reduce ? 0.0 : 1.0;
    phaseA += dt * 0.35 * spin * motion;
    phaseB += dt * 0.22 * spin * motion;
    chaseHead += dt * 2.6 * motion;

    for (var i = ripples.length - 1; i >= 0; i--) {
      ripples[i] += dt;
      if (ripples[i] > rippleLife) ripples.removeAt(i);
    }
    if (flashAge >= 0) {
      flashAge += dt;
      if (flashAge > flashLife) flashAge = -1;
    }
    notifyListeners();
  }
}

class _ReactorPainter extends CustomPainter {
  _ReactorPainter(this.f) : super(repaint: f);
  final _Frame f;

  static double _stage(double x, double a, double b) {
    final v = ((x - a) / (b - a)).clamp(0.0, 1.0);
    return 1 - math.pow(1 - v, 3).toDouble();
  }

  @override
  void paint(Canvas canvas, Size size) {
    final R = size.shortestSide / 2;
    final c = size.center(Offset.zero);
    final tint = f.tint;
    final dim = f.dim;
    final ring = _stage(f.ignition, 0.05, 0.55);
    final segS = _stage(f.ignition, 0.25, 0.80);
    final nuc = _stage(f.ignition, 0.45, 1.0);
    final flashP = f.flashAge < 0 ? 1.0 : f.flashAge / _Frame.flashLife;
    final flashBoost = f.flashAge < 0 ? 0.0 : (1 - flashP);

    canvas.save();
    canvas.translate(c.dx, c.dy);

    // 1 — halo
    final haloR = R * 0.98;
    canvas.drawCircle(
      Offset.zero,
      haloR,
      Paint()
        ..shader = RadialGradient(colors: [
          tint.withValues(alpha: (0.10 + 0.10 * f.glow + 0.08 * f.energy + 0.12 * flashBoost) * dim * nuc),
          tint.withValues(alpha: 0),
        ]).createShader(Rect.fromCircle(center: Offset.zero, radius: haloR)),
    );

    final stroke = Paint()..style = PaintingStyle.stroke;

    // 2 — outer hairline + four cardinal marks (no degree numbers: R1)
    stroke
      ..strokeWidth = 1
      ..color = tint.withValues(alpha: 0.13 * dim * ring);
    canvas.drawCircle(Offset.zero, R * 0.94 * (0.9 + 0.1 * ring), stroke);
    final card = Path();
    for (var i = 0; i < 4; i++) {
      final a = i * math.pi / 2 - math.pi / 2;
      card
        ..moveTo(math.cos(a) * R * 0.91, math.sin(a) * R * 0.91)
        ..lineTo(math.cos(a) * R * 0.97, math.sin(a) * R * 0.97);
    }
    canvas.drawPath(
        card,
        stroke
          ..strokeWidth = 1.5
          ..color = tint.withValues(alpha: 0.55 * dim * ring));

    // 3 — fine tick ring, slow drift
    final ticks = Path();
    const nT = 90;
    final rot = f.phaseB * 0.15;
    for (var i = 0; i < nT; i++) {
      if (i / nT > ring) break;
      final a = i / nT * math.pi * 2 + rot;
      final long = i % 15 == 0;
      final r1 = R * (long ? 0.835 : 0.85), r2 = R * 0.865;
      ticks
        ..moveTo(math.cos(a) * r1, math.sin(a) * r1)
        ..lineTo(math.cos(a) * r2, math.sin(a) * r2);
    }
    canvas.drawPath(
        ticks,
        stroke
          ..strokeWidth = 1
          ..color = tint.withValues(alpha: 0.16 * dim));

    // 4 — counter-rotating arcs (with a bright head on arc A)
    final rA = R * 0.76, rB = R * 0.685;
    final rectA = Rect.fromCircle(center: Offset.zero, radius: rA);
    final rectB = Rect.fromCircle(center: Offset.zero, radius: rB);
    stroke
      ..strokeCap = StrokeCap.round
      ..strokeWidth = 1.6
      ..color = tint.withValues(alpha: 0.75 * dim * ring);
    canvas.drawArc(rectA, f.phaseA, 1.15 * ring, false, stroke);
    canvas.drawArc(rectA, f.phaseA + math.pi, 0.5 * ring, false, stroke);
    final head = f.phaseA + 1.15 * ring;
    canvas.drawCircle(Offset(math.cos(head) * rA, math.sin(head) * rA), 2.2,
        Paint()..color = C.cyanHot.withValues(alpha: 0.9 * dim * ring));
    stroke
      ..strokeWidth = 1
      ..color = tint.withValues(alpha: 0.35 * dim * ring);
    canvas.drawArc(rectB, -f.phaseB, 0.85 * ring, false, stroke);
    canvas.drawArc(rectB, -f.phaseB + 2.4, 0.32 * ring, false, stroke);
    stroke.strokeCap = StrokeCap.butt;

    // 5 — segment ring: becomes a spectrum while listening/speaking
    const nS = 56;
    final r0 = R * 0.50, r1 = R * 0.565;
    final segW = (2 * math.pi * r0 / nS) * 0.5;
    final seg = Paint()
      ..strokeWidth = segW
      ..strokeCap = StrokeCap.butt;
    final head2 = f.chaseHead % (math.pi * 2);
    for (var i = 0; i < nS; i++) {
      if (i / nS > segS) break;
      final a = i / nS * math.pi * 2 - math.pi / 2;
      final n = 0.5 +
          0.5 * math.sin(f.t * 3.1 + i * 1.7) * math.cos(f.t * 1.3 + i * 0.63);
      final ext = R * 0.18 * f.spectrum * f.energy * n;
      var d = (a + math.pi / 2 - head2) % (math.pi * 2);
      if (d < 0) d += math.pi * 2;
      final chaseLit = f.chase * math.max(0.0, 1 - d / 1.4);
      final lit = (0.22 + 0.55 * f.spectrum * f.energy * n + 0.7 * chaseLit).clamp(0.0, 1.0);
      seg.color = Color.lerp(tint, C.cyanHot, chaseLit * 0.6)!.withValues(alpha: lit * dim);
      canvas.drawLine(Offset(math.cos(a) * r0, math.sin(a) * r0),
          Offset(math.cos(a) * (r1 + ext), math.sin(a) * (r1 + ext)), seg);
    }

    // 6 — inner ring + quiet lattice
    stroke
      ..strokeWidth = 1
      ..color = tint.withValues(alpha: 0.28 * dim * segS);
    canvas.drawCircle(Offset.zero, R * 0.43, stroke);
    // a single slowly turning hexagon with lit vertices (not two triangles —
    // overlapped triangles read as a religious symbol)
    final lat = Path();
    final lr = R * 0.36, lrot = -f.phaseA * 0.25;
    final verts = <Offset>[];
    for (var v = 0; v < 6; v++) {
      final a = lrot + v * math.pi / 3 - math.pi / 2;
      final p = Offset(math.cos(a) * lr, math.sin(a) * lr);
      verts.add(p);
      v == 0 ? lat.moveTo(p.dx, p.dy) : lat.lineTo(p.dx, p.dy);
    }
    lat.close();
    final vdot = Paint()..color = tint.withValues(alpha: 0.5 * dim * segS);
    for (final p in verts) {
      canvas.drawCircle(p, 1.6, vdot);
    }
    canvas.drawPath(
        lat,
        stroke
          ..strokeWidth = 0.8
          ..color = tint.withValues(alpha: 0.14 * dim * segS));

    // 7 — nucleus
    final breath = 0.5 + 0.5 * math.sin(f.t * 1.6);
    final nr = R * 0.21 * (1 + 0.05 * breath + 0.22 * f.energy + 0.15 * flashBoost) * (0.4 + 0.6 * nuc);
    canvas.drawCircle(
      Offset.zero,
      nr,
      Paint()
        ..shader = RadialGradient(colors: [
          C.cyanHot.withValues(alpha: (0.55 + 0.45 * f.glow) * dim * nuc),
          tint.withValues(alpha: 0.45 * f.glow * dim * nuc),
          tint.withValues(alpha: 0),
        ], stops: const [0.0, 0.38, 1.0]).createShader(Rect.fromCircle(center: Offset.zero, radius: nr)),
    );
    canvas.drawCircle(
        Offset.zero,
        R * 0.075 * (1 + 0.15 * f.energy) * nuc,
        Paint()..color = Color.lerp(C.cyanHot, Colors.white, 0.4)!.withValues(alpha: (0.5 + 0.5 * f.glow) * dim));

    // 8 — ripples (one per spoken word)
    for (final age in f.ripples) {
      final p = age / _Frame.rippleLife;
      final e = 1 - math.pow(1 - p, 2).toDouble();
      stroke
        ..strokeWidth = 1.4 * (1 - p)
        ..color = tint.withValues(alpha: 0.45 * (1 - p) * dim);
      canvas.drawCircle(Offset.zero, R * (0.46 + 0.52 * e), stroke);
    }

    // 9 — state flash (wake / success / error / needs-OK)
    if (f.flashAge >= 0) {
      final e = 1 - math.pow(1 - flashP, 3).toDouble();
      stroke
        ..strokeWidth = 2.4 * (1 - flashP)
        ..color = f.flashColor.withValues(alpha: 0.85 * (1 - flashP));
      canvas.drawCircle(Offset.zero, R * (0.5 + 0.48 * e), stroke);
    }

    canvas.restore();
  }

  @override
  bool shouldRepaint(covariant _ReactorPainter old) => old.f != f;
}
