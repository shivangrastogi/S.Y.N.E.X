import 'dart:math' as math;

import 'package:flutter/material.dart';

import '../tokens.dart';

/// Static app background: radial haze + a very faint dot grid. Painted once
/// (RepaintBoundary, shouldRepaint false) — it never animates.
class HudBackground extends StatelessWidget {
  const HudBackground({super.key, this.child, this.hazeAt = const Alignment(0, -0.35)});
  final Widget? child;
  final Alignment hazeAt;

  @override
  Widget build(BuildContext context) {
    return Stack(fit: StackFit.expand, children: [
      RepaintBoundary(child: CustomPaint(painter: _BgPainter(hazeAt))),
      ?child,
    ]);
  }
}

class _BgPainter extends CustomPainter {
  _BgPainter(this.hazeAt);
  final Alignment hazeAt;

  @override
  void paint(Canvas canvas, Size size) {
    final rect = Offset.zero & size;
    canvas.drawRect(rect, Paint()..color = C.bg);
    final c = hazeAt.alongSize(size);
    final r = size.longestSide * 0.62;
    canvas.drawCircle(
      c,
      r,
      Paint()
        ..shader = RadialGradient(colors: [
          C.haze.withValues(alpha: 0.85),
          C.haze.withValues(alpha: 0.0),
        ], stops: const [0.0, 1.0])
            .createShader(Rect.fromCircle(center: c, radius: r)),
    );
    // dot grid, fades out toward the bottom
    const step = 22.0;
    final dot = Paint()..color = C.cyan;
    for (double y = step; y < size.height; y += step) {
      final fade = (1 - (y / size.height)).clamp(0.0, 1.0);
      dot.color = C.cyan.withValues(alpha: 0.035 * (0.35 + 0.65 * fade));
      for (double x = step / 2; x < size.width; x += step) {
        canvas.drawCircle(Offset(x, y), 0.7, dot);
      }
    }
  }

  @override
  bool shouldRepaint(covariant _BgPainter old) => old.hazeAt != hazeAt;
}

/// The one quiet HUD cue: a 6px chamfer on the top-right and bottom-left.
class ChamferBorder extends OutlinedBorder {
  const ChamferBorder({this.cut = 6, super.side = const BorderSide(color: C.hairline)});
  final double cut;

  Path _path(Rect r) {
    final c = math.min(cut, r.shortestSide / 3);
    return Path()
      ..moveTo(r.left, r.top)
      ..lineTo(r.right - c, r.top)
      ..lineTo(r.right, r.top + c)
      ..lineTo(r.right, r.bottom)
      ..lineTo(r.left + c, r.bottom)
      ..lineTo(r.left, r.bottom - c)
      ..close();
  }

  @override
  Path getOuterPath(Rect rect, {TextDirection? textDirection}) => _path(rect);
  @override
  Path getInnerPath(Rect rect, {TextDirection? textDirection}) =>
      _path(rect.deflate(side.width));
  @override
  void paint(Canvas canvas, Rect rect, {TextDirection? textDirection}) {
    if (side.style == BorderStyle.none) return;
    canvas.drawPath(
        _path(rect.deflate(side.width / 2)),
        Paint()
          ..style = PaintingStyle.stroke
          ..strokeWidth = side.width
          ..color = side.color);
  }

  @override
  ShapeBorder scale(double t) => ChamferBorder(cut: cut * t, side: side.scale(t));
  @override
  ChamferBorder copyWith({BorderSide? side}) =>
      ChamferBorder(cut: cut, side: side ?? this.side);
  @override
  EdgeInsetsGeometry get dimensions => EdgeInsets.all(side.width);
}

/// Flat panel. No brackets — brackets mark focus only (see [Brackets]).
class Panel extends StatelessWidget {
  const Panel({
    super.key,
    required this.child,
    this.padding = const EdgeInsets.all(S.lg),
    this.onTap,
    this.borderColor = C.hairline,
    this.fill = C.surface,
  });
  final Widget child;
  final EdgeInsets padding;
  final VoidCallback? onTap;
  final Color borderColor;
  final Color fill;

  @override
  Widget build(BuildContext context) {
    final shape = ChamferBorder(side: BorderSide(color: borderColor));
    return Material(
      color: fill,
      shape: shape,
      clipBehavior: Clip.antiAlias,
      child: InkWell(
        onTap: onTap,
        splashColor: C.cyan.withValues(alpha: 0.06),
        child: Padding(padding: padding, child: child),
      ),
    );
  }
}

/// Four L-shaped corner brackets around [child]. Use ONLY for the element
/// that has focus or needs a decision (reactor frame, approval).
class Brackets extends StatelessWidget {
  const Brackets({
    super.key,
    required this.child,
    this.color = C.cyan,
    this.arm = 12,
    this.inset = -4,
  });
  final Widget child;
  final Color color;
  final double arm;
  final double inset;

  @override
  Widget build(BuildContext context) => CustomPaint(
        foregroundPainter: _BracketPainter(color, arm, inset),
        child: child,
      );
}

class _BracketPainter extends CustomPainter {
  _BracketPainter(this.color, this.arm, this.inset);
  final Color color;
  final double arm, inset;

  @override
  void paint(Canvas canvas, Size size) {
    final p = Paint()
      ..color = color
      ..strokeWidth = 1.5
      ..style = PaintingStyle.stroke
      ..strokeCap = StrokeCap.square;
    final l = inset, t = inset, r = size.width - inset, b = size.height - inset;
    void corner(double x, double y, double dx, double dy) {
      canvas.drawPath(
          Path()
            ..moveTo(x, y + dy * arm)
            ..lineTo(x, y)
            ..lineTo(x + dx * arm, y),
          p);
    }

    corner(l, t, 1, 1);
    corner(r, t, -1, 1);
    corner(l, b, 1, -1);
    corner(r, b, -1, -1);
  }

  @override
  bool shouldRepaint(covariant _BracketPainter o) =>
      o.color != color || o.arm != arm || o.inset != inset;
}
