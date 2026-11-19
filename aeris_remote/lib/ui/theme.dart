import 'dart:math' as math;
import 'package:flutter/material.dart';

/// AERIS "Aurora Pro" — design tokens, the Material theme, and the presence
/// sphere. Calm graphite surfaces, ONE cool accent (arc-reactor ice blue),
/// Sora for UI text and IBM Plex Mono for HUD labels and real data
/// (times, numbers, model ids). Colour is information, never decoration:
/// accent = AERIS acting/listening, mint = OK, amber = needs you, red = stop.
/// Design: the "AERIS Mobile Redesign" canvas, Aurora Pro row.
class A {
  // Surfaces — blue-black graphite, never pure #000.
  static const deck = Color(0xFF080A0F);
  static const panel = Color(0xFF0F131A);
  static const panelHi = Color(0xFF161C27);
  static const line = Color(0xFF1E2430);

  // Signals.
  static const accent = Color(0xFF7FD4FF); // AERIS acting / listening
  static const accentSoft = Color(0xFF9AB8FF); // secondary, rare
  static const ok = Color(0xFF5FE3B5); // ready / done
  static const warn = Color(0xFFFFC489); // needs attention
  static const hot = Color(0xFFFF6B6B); // stop / destructive

  // Ink.
  static const text = Color(0xFFE8ECF2);
  static const muted = Color(0xFF9AA4B2);
  static const faint = Color(0xFF5F6977);
  static const onLight = Color(0xFF0B0F16); // text on a light button

  /// For the few gradient-filled controls: a quiet blue blend.
  static const gradient = LinearGradient(
    colors: [Color(0xFF7FD4FF), Color(0xFF9AB8FF)],
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
  );

  static const sans = 'Sora';
  static const mono = 'PlexMono';

  static const radius = 16.0;

  /// The small ALL-CAPS HUD label (encodes section, not decoration).
  static Widget label(String s, {Color? color}) => Text(
        s.toUpperCase(),
        style: TextStyle(
          fontFamily: mono,
          fontSize: 10.5,
          letterSpacing: 1.4,
          fontWeight: FontWeight.w500,
          color: color ?? faint,
        ),
      );

  /// The app-wide Material theme.
  static ThemeData theme() {
    final base = ThemeData(
      brightness: Brightness.dark,
      useMaterial3: true,
      fontFamily: sans,
      scaffoldBackgroundColor: deck,
      colorScheme: const ColorScheme.dark(
        primary: accent,
        onPrimary: onLight,
        secondary: accentSoft,
        surface: panel,
        onSurface: text,
        surfaceContainerHighest: panelHi,
        outline: line,
        error: hot,
      ),
      splashFactory: InkSparkle.splashFactory,
    );
    return base.copyWith(
      appBarTheme: const AppBarTheme(
        backgroundColor: deck,
        surfaceTintColor: Colors.transparent,
        elevation: 0,
        scrolledUnderElevation: 0,
        centerTitle: false,
        iconTheme: IconThemeData(color: muted),
        titleTextStyle: TextStyle(fontFamily: sans, fontSize: 18, fontWeight: FontWeight.w500, color: text),
      ),
      dividerTheme: const DividerThemeData(color: line, thickness: 1, space: 1),
      listTileTheme: const ListTileThemeData(
        iconColor: muted,
        textColor: text,
        minVerticalPadding: 12,
        contentPadding: EdgeInsets.symmetric(horizontal: 16),
      ),
      switchTheme: SwitchThemeData(
        thumbColor: WidgetStateProperty.resolveWith((s) => s.contains(WidgetState.selected) ? onLight : muted),
        trackColor: WidgetStateProperty.resolveWith((s) => s.contains(WidgetState.selected) ? accent : panelHi),
        trackOutlineColor: WidgetStateProperty.resolveWith((s) => s.contains(WidgetState.selected) ? accent : line),
      ),
      radioTheme: RadioThemeData(
        fillColor: WidgetStateProperty.resolveWith((s) => s.contains(WidgetState.selected) ? accent : muted),
      ),
      segmentedButtonTheme: SegmentedButtonThemeData(
        style: ButtonStyle(
          backgroundColor: WidgetStateProperty.resolveWith((s) => s.contains(WidgetState.selected) ? panelHi : Colors.transparent),
          foregroundColor: WidgetStateProperty.resolveWith((s) => s.contains(WidgetState.selected) ? text : muted),
          side: const WidgetStatePropertyAll(BorderSide(color: line)),
          shape: WidgetStatePropertyAll(RoundedRectangleBorder(borderRadius: BorderRadius.circular(12))),
          textStyle: const WidgetStatePropertyAll(TextStyle(fontFamily: sans, fontSize: 13.5)),
        ),
      ),
      filledButtonTheme: FilledButtonThemeData(
        style: FilledButton.styleFrom(
          backgroundColor: text,
          foregroundColor: onLight,
          disabledBackgroundColor: panelHi,
          disabledForegroundColor: faint,
          minimumSize: const Size(64, 46),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
          textStyle: const TextStyle(fontFamily: sans, fontSize: 14.5, fontWeight: FontWeight.w600),
        ),
      ),
      outlinedButtonTheme: OutlinedButtonThemeData(
        style: OutlinedButton.styleFrom(
          foregroundColor: text,
          side: const BorderSide(color: line),
          minimumSize: const Size(64, 46),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
          textStyle: const TextStyle(fontFamily: sans, fontSize: 14.5),
        ),
      ),
      textButtonTheme: TextButtonThemeData(
        style: TextButton.styleFrom(
          foregroundColor: accent,
          textStyle: const TextStyle(fontFamily: sans, fontSize: 14, fontWeight: FontWeight.w500),
        ),
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: panel,
        labelStyle: const TextStyle(color: muted),
        hintStyle: const TextStyle(color: faint),
        helperStyle: const TextStyle(color: faint, fontSize: 11.5),
        contentPadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 16),
        border: OutlineInputBorder(borderRadius: BorderRadius.circular(12), borderSide: const BorderSide(color: line)),
        enabledBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(12), borderSide: const BorderSide(color: line)),
        focusedBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(12), borderSide: const BorderSide(color: accent, width: 1.5)),
        errorBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(12), borderSide: const BorderSide(color: hot)),
      ),
      snackBarTheme: SnackBarThemeData(
        behavior: SnackBarBehavior.floating,
        backgroundColor: panelHi,
        contentTextStyle: const TextStyle(fontFamily: sans, color: text, fontSize: 14),
        actionTextColor: accent,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      ),
      dialogTheme: DialogThemeData(
        backgroundColor: panelHi,
        surfaceTintColor: Colors.transparent,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
        titleTextStyle: const TextStyle(fontFamily: sans, fontSize: 18, fontWeight: FontWeight.w500, color: text),
        contentTextStyle: const TextStyle(fontFamily: sans, fontSize: 14, color: muted, height: 1.45),
      ),
      bottomSheetTheme: const BottomSheetThemeData(
        backgroundColor: panelHi,
        surfaceTintColor: Colors.transparent,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.vertical(top: Radius.circular(20))),
      ),
      progressIndicatorTheme: const ProgressIndicatorThemeData(color: accent, linearTrackColor: panelHi),
      popupMenuTheme: PopupMenuThemeData(
        color: panelHi,
        surfaceTintColor: Colors.transparent,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
        textStyle: const TextStyle(fontFamily: sans, color: text, fontSize: 14),
      ),
    );
  }
}

/// The AERIS presence sphere — a glass sphere inside a HUD tick ring. Its
/// state IS the assistant: a slow breath when idle, a rotating accent arc
/// and brighter glow when listening/working, desaturated grey when asleep.
/// Manages its own ticker; respects reduced motion.
class AerisOrb extends StatefulWidget {
  final double size;
  final bool online;
  final bool active; // listening / working → arc spins, glow brightens

  const AerisOrb({
    super.key,
    this.size = 40,
    this.online = false,
    this.active = false,
  });

  @override
  State<AerisOrb> createState() => _AerisOrbState();
}

class _AerisOrbState extends State<AerisOrb> with SingleTickerProviderStateMixin {
  late final AnimationController _c;

  @override
  void initState() {
    super.initState();
    _c = AnimationController(vsync: this, duration: const Duration(milliseconds: 4000))..repeat();
    _sync();
  }

  void _sync() {
    _c.duration = Duration(milliseconds: widget.active ? 1600 : 4000);
    if (widget.online || widget.active) {
      if (!_c.isAnimating) _c.repeat();
    } else {
      _c.stop();
      _c.value = 0.25;
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
    // Own layer: the sphere animates every frame; without a boundary each
    // frame also repainted whatever screen it sits in.
    return RepaintBoundary(
      child: AnimatedBuilder(
        animation: _c,
        builder: (_, __) => CustomPaint(
          size: Size.square(widget.size),
          painter: _OrbPainter(t: reduce ? 0.25 : _c.value, online: widget.online, active: widget.active),
        ),
      ),
    );
  }
}

class _OrbPainter extends CustomPainter {
  final double t; // 0..1, one full turn
  final bool online;
  final bool active;
  _OrbPainter({required this.t, required this.online, required this.active});

  @override
  void paint(Canvas canvas, Size size) {
    final c = size.center(Offset.zero);
    final r = size.width / 2;
    final live = online || active;
    final breathe = 0.5 + 0.5 * math.sin(t * 2 * math.pi); // 0..1
    final small = size.width < 48; // header/avatar sizes: no HUD ring

    // Soft glow under the sphere.
    if (live) {
      final a = (active ? 0.26 : 0.14) * (0.75 + 0.25 * breathe);
      canvas.drawCircle(
          c,
          r,
          Paint()
            ..shader = RadialGradient(colors: [A.accent.withValues(alpha: a), A.accent.withValues(alpha: 0)])
                .createShader(Rect.fromCircle(center: c, radius: r)));
    }

    // HUD tick ring.
    if (!small) {
      final ticks = Paint()
        ..color = A.text.withValues(alpha: live ? 0.26 : 0.12)
        ..strokeWidth = math.max(1.0, r * 0.012);
      const n = 60;
      for (var i = 0; i < n; i++) {
        final ang = i / n * 2 * math.pi;
        final long = i % 5 == 0;
        final r1 = r * 0.95, r2 = r * (long ? 0.87 : 0.90);
        canvas.drawLine(c + Offset(math.cos(ang), math.sin(ang)) * r1,
            c + Offset(math.cos(ang), math.sin(ang)) * r2, ticks);
      }
      // Rotating accent arc — the "working" signal.
      if (live) {
        final arc = Paint()
          ..style = PaintingStyle.stroke
          ..strokeWidth = math.max(1.5, r * 0.018)
          ..strokeCap = StrokeCap.round
          ..color = A.accent.withValues(alpha: active ? 0.85 : 0.45);
        canvas.drawArc(Rect.fromCircle(center: c, radius: r * 0.985), t * 2 * math.pi - math.pi / 2,
            active ? math.pi * 0.55 : math.pi * 0.3, false, arc);
      }
    }

    // The glass sphere.
    final sr = r * (small ? 0.92 : 0.62) * (0.97 + 0.03 * (live ? breathe : 0.5));
    final rect = Rect.fromCircle(center: c, radius: sr);
    final colors = live
        ? const [Color(0xFFA9DDF5), Color(0xFF3E6F94), Color(0xFF13202F), Color(0xFF0A1018)]
        : const [Color(0xFF8C939E), Color(0xFF3A404A), Color(0xFF181B21), Color(0xFF0C0E12)];
    canvas.drawCircle(
        c,
        sr,
        Paint()
          ..shader = RadialGradient(
            center: const Alignment(0, 0.15),
            radius: 0.95,
            colors: colors,
            stops: const [0.0, 0.45, 0.8, 1.0],
          ).createShader(rect));
    // Specular highlight — what makes it read as glass.
    final hc = c + Offset(-sr * 0.34, -sr * 0.42);
    canvas.drawCircle(
        hc,
        sr * 0.42,
        Paint()
          ..shader = RadialGradient(colors: [Colors.white.withValues(alpha: live ? 0.85 : 0.45), Colors.white.withValues(alpha: 0)])
              .createShader(Rect.fromCircle(center: hc, radius: sr * 0.42)));
    // Thin rim.
    canvas.drawCircle(
        c,
        sr,
        Paint()
          ..style = PaintingStyle.stroke
          ..strokeWidth = 1
          ..color = A.text.withValues(alpha: 0.10));
  }

  @override
  bool shouldRepaint(covariant _OrbPainter o) => o.t != t || o.online != online || o.active != active;
}
