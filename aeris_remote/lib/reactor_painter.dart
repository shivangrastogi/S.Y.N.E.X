// The AERIS arc-reactor — Iron-Man HUD, cyberpunk. Ported from the approved
// web prototype (claude.ai artifact) to a Flutter CustomPainter so it's crisp
// at any size, tiny, theme-reactive, and driven by REAL mic amplitude.
//
// One painter drives both experiences:
//   • cinematic  — full-screen ignition (app-open / power-button assist)
//   • compact    — small live core (everyday "Aeris" wake, bottom overlay)
// `ignition` (0..1) runs the boot choreography; at 1.0 it's the live idle.
import 'dart:math' as math;
import 'dart:ui' as ui;
import 'package:flutter/material.dart';

class Reactor {
  static const arc = Color(0xFF37E0EA);
  static const violet = Color(0xFF7C6CFF);
  static const mint = Color(0xFF54F0C0);
  static const amber = Color(0xFFFFB454);
  static const white = Color(0xFFEAF7FF);

  static double _ease(double t) => 1 - math.pow(1 - t.clamp(0, 1), 3).toDouble();
  static double _seg(double e, double a, double b) =>
      ((e - a) / (b - a)).clamp(0.0, 1.0);

  /// Paint the reactor centered in [size].
  /// [t] seconds (continuous), [ignition] 0..1, [amp] 0..1, [accent] core hue.
  static void paint(Canvas canvas, Size size,
      {required double t,
      required double ignition,
      required double amp,
      required Color accent}) {
    final cx = size.width / 2, cy = size.height / 2;
    final r = math.min(size.width, size.height) * 0.20;
    canvas.save();
    canvas.translate(cx, cy);

    final live = ignition >= 1.0;
    final oRings = _ease(_seg(ignition, 0.12, 0.55));
    final oCore = _ease(_seg(ignition, 0.32, 0.60));
    final oSpokes = _ease(_seg(ignition, 0.42, 0.82));

    // ── outer tick ring (rotates into place) ──
    final tickRot = t * 0.12 + (1 - oRings) * 0.6;
    final tp = Paint()..strokeCap = StrokeCap.butt;
    for (var i = 0; i < 60; i++) {
      final a = (i / 60) * math.pi * 2 + tickRot;
      final long = i % 5 == 0, accentTick = i % 15 == 0;
      final r1 = r * 1.62 * (long ? 0.955 : 0.975), r2 = r * 1.62;
      tp
        ..color = (accentTick ? amber : arc)
            .withValues(alpha: oRings * (accentTick ? 0.85 : long ? 0.5 : 0.22))
        ..strokeWidth = accentTick ? 2 : 1;
      canvas.drawLine(Offset(math.cos(a) * r1, math.sin(a) * r1),
          Offset(math.cos(a) * r2, math.sin(a) * r2), tp);
    }

    // ── concentric dashed arc rings (counter-rotating) ──
    _arcRing(canvas, r * 1.40, t * 0.35, [.0, .20, .34, .52, .70, .88], arc, 1.6,
        oRings * 0.8);
    _arcRing(canvas, r * 1.14, -t * 0.55, [.05, .30, .55, .74], violet, 1.4,
        oRings * 0.7);
    _arcRing(canvas, r * 0.92, t * 0.9, [.1, .22, .5, .63, .8, .9], arc, 1.0,
        oRings * 0.5);

    // ── scan-lock sweep ──
    final sweepA = live ? (t * 0.6) % (math.pi * 2) : ignition * math.pi * 2 * 1.4;
    final sweepAlpha = live ? 0.35 : (1 - _seg(ignition, 0, 0.35)) * 0.9 + 0.25;
    _gradArc(canvas, r * 1.40, sweepA, 0.5, arc, sweepAlpha);

    // ── radial spokes (reactive to amplitude) ──
    final sp = Paint()..strokeCap = StrokeCap.round;
    const nS = 48;
    for (var i = 0; i < nS; i++) {
      final a = (i / nS) * math.pi * 2;
      final wob = 0.5 + 0.5 * math.sin(t * 2.2 * (live ? 1 : 0) + i * 0.7);
      final len = r * (0.30 + amp * 0.85 * wob);
      final r1 = r * 0.66;
      final amberSpoke = i % 12 == 0;
      sp
        ..color = (amberSpoke ? amber : accent)
            .withValues(alpha: oSpokes * (0.35 + amp * 0.55))
        ..strokeWidth = amberSpoke ? 2.4 : 2;
      canvas.drawLine(Offset(math.cos(a) * r1, math.sin(a) * r1),
          Offset(math.cos(a) * (r1 + len), math.sin(a) * (r1 + len)), sp);
    }

    // ── core bloom ──
    final coreR = r * (0.52 + amp * 0.14);
    final g = ui.Gradient.radial(Offset.zero, coreR * 2.4, [
      white.withValues(alpha: 0.9 * oCore),
      arc.withValues(alpha: 0.85 * oCore),
      violet.withValues(alpha: 0.28 * oCore),
      violet.withValues(alpha: 0.0),
    ], [
      0.0,
      0.18,
      0.5,
      1.0
    ]);
    canvas.drawCircle(Offset.zero, coreR * 2.4, Paint()..shader = g);
    canvas.drawCircle(Offset.zero, coreR * 0.34,
        Paint()..color = white.withValues(alpha: 0.95 * oCore));
    for (var k = 1; k <= 3; k++) {
      canvas.drawCircle(
          Offset.zero,
          coreR * (0.5 + k * 0.16),
          Paint()
            ..style = PaintingStyle.stroke
            ..strokeWidth = 1
            ..color = arc.withValues(alpha: oCore * (0.5 - k * 0.1)));
    }

    // ── amber targeting reticle ──
    final retA = live ? 0.16 : _ease(_seg(ignition, 0.3, 0.6)) * 0.9;
    final rp = Paint()
      ..color = amber.withValues(alpha: retA)
      ..strokeWidth = 1.2
      ..style = PaintingStyle.stroke;
    final rr = r * 0.44, gap = r * 0.13;
    canvas.drawLine(Offset(-rr, 0), Offset(-gap, 0), rp);
    canvas.drawLine(Offset(gap, 0), Offset(rr, 0), rp);
    canvas.drawLine(Offset(0, -rr), Offset(0, -gap), rp);
    canvas.drawLine(Offset(0, gap), Offset(0, rr), rp);
    canvas.drawCircle(Offset.zero, r * 0.62, rp);

    canvas.restore();
  }

  static void _arcRing(Canvas c, double r, double rot, List<double> segs,
      Color col, double lw, double alpha) {
    final p = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = lw
      ..color = col.withValues(alpha: alpha);
    final rect = Rect.fromCircle(center: Offset.zero, radius: r);
    for (var i = 0; i < segs.length; i += 2) {
      final s = segs[i] * math.pi * 2 + rot;
      final e = segs[i + 1] * math.pi * 2 + rot;
      c.drawArc(rect, s, e - s, false, p);
    }
  }

  static void _gradArc(
      Canvas c, double r, double start, double width, Color col, double alpha) {
    const steps = 26;
    final rect = Rect.fromCircle(center: Offset.zero, radius: r);
    final p = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = 2.4
      ..strokeCap = StrokeCap.round;
    for (var i = 0; i < steps; i++) {
      final a = start + (i / steps) * width;
      p.color = col.withValues(alpha: alpha * (i / steps));
      c.drawArc(rect, a, width / steps + 0.01, false, p);
    }
  }
}
