import 'package:flutter/material.dart';

import 'tokens.dart';

/// Palette resolved for one brightness. Widgets read this instead of reaching
/// into [T] directly, so a single lookup works in either theme.
@immutable
class AerisPalette extends ThemeExtension<AerisPalette> {
  const AerisPalette({
    required this.ground,
    required this.surface,
    required this.surfaceHi,
    required this.line,
    required this.ink,
    required this.inkDim,
    required this.tierDevice,
    required this.tierLaptop,
    required this.tierCloud,
    required this.danger,
  });

  final Color ground;
  final Color surface;
  final Color surfaceHi;
  final Color line;
  final Color ink;
  final Color inkDim;
  final Color tierDevice;
  final Color tierLaptop;
  final Color tierCloud;
  final Color danger;

  static const dark = AerisPalette(
    ground: T.groundDark,
    surface: T.surfaceDark,
    surfaceHi: T.surfaceHiDark,
    line: T.lineDark,
    ink: T.inkDark,
    inkDim: T.inkDimDark,
    tierDevice: T.tierDevice,
    tierLaptop: T.tierLaptop,
    tierCloud: T.tierCloud,
    danger: T.danger,
  );

  static const light = AerisPalette(
    ground: T.groundLight,
    surface: T.surfaceLight,
    surfaceHi: T.surfaceHiLight,
    line: T.lineLight,
    ink: T.inkLight,
    inkDim: T.inkDimLight,
    tierDevice: T.tierDeviceLight,
    tierLaptop: T.tierLaptopLight,
    tierCloud: T.tierCloudLight,
    danger: Color(0xFFB4342A),
  );

  /// Palette for the current context. Falls back to dark if the extension is
  /// missing, which only happens in a widget test that builds a bare MaterialApp.
  static AerisPalette of(BuildContext context) =>
      Theme.of(context).extension<AerisPalette>() ?? dark;

  @override
  AerisPalette copyWith({
    Color? ground,
    Color? surface,
    Color? surfaceHi,
    Color? line,
    Color? ink,
    Color? inkDim,
    Color? tierDevice,
    Color? tierLaptop,
    Color? tierCloud,
    Color? danger,
  }) {
    return AerisPalette(
      ground: ground ?? this.ground,
      surface: surface ?? this.surface,
      surfaceHi: surfaceHi ?? this.surfaceHi,
      line: line ?? this.line,
      ink: ink ?? this.ink,
      inkDim: inkDim ?? this.inkDim,
      tierDevice: tierDevice ?? this.tierDevice,
      tierLaptop: tierLaptop ?? this.tierLaptop,
      tierCloud: tierCloud ?? this.tierCloud,
      danger: danger ?? this.danger,
    );
  }

  @override
  AerisPalette lerp(ThemeExtension<AerisPalette>? other, double t) {
    if (other is! AerisPalette) return this;
    return AerisPalette(
      ground: Color.lerp(ground, other.ground, t)!,
      surface: Color.lerp(surface, other.surface, t)!,
      surfaceHi: Color.lerp(surfaceHi, other.surfaceHi, t)!,
      line: Color.lerp(line, other.line, t)!,
      ink: Color.lerp(ink, other.ink, t)!,
      inkDim: Color.lerp(inkDim, other.inkDim, t)!,
      tierDevice: Color.lerp(tierDevice, other.tierDevice, t)!,
      tierLaptop: Color.lerp(tierLaptop, other.tierLaptop, t)!,
      tierCloud: Color.lerp(tierCloud, other.tierCloud, t)!,
      danger: Color.lerp(danger, other.danger, t)!,
    );
  }
}

class AerisTheme {
  const AerisTheme._();

  static ThemeData dark() => _build(Brightness.dark, AerisPalette.dark);
  static ThemeData light() => _build(Brightness.light, AerisPalette.light);

  static ThemeData _build(Brightness brightness, AerisPalette p) {
    final base = ThemeData(brightness: brightness, useMaterial3: true);

    TextStyle sans(double size, FontWeight weight, Color color,
            {double spacing = 0, double height = 1.35}) =>
        TextStyle(
          fontFamilyFallback: T.sans,
          fontSize: size,
          fontWeight: weight,
          color: color,
          letterSpacing: spacing,
          height: height,
        );

    return base.copyWith(
      scaffoldBackgroundColor: p.ground,
      colorScheme: base.colorScheme.copyWith(
        primary: p.tierLaptop,
        surface: p.surface,
        error: p.danger,
      ),
      dividerColor: p.line,
      textTheme: base.textTheme.copyWith(
        titleMedium: sans(15, FontWeight.w600, p.ink, spacing: 0.2),
        bodyLarge: sans(15, FontWeight.w400, p.ink, height: 1.45),
        bodyMedium: sans(14, FontWeight.w400, p.ink, height: 1.45),
        bodySmall: sans(12.5, FontWeight.w400, p.inkDim),
        labelSmall: TextStyle(
          fontFamilyFallback: T.mono,
          fontSize: 10.5,
          fontWeight: FontWeight.w600,
          letterSpacing: 0.9,
          color: p.inkDim,
        ),
      ),
      extensions: <ThemeExtension<dynamic>>[p],
    );
  }

  /// The instrument-readout style: tier names, latency, timestamps. Monospace
  /// so digits line up as values change in place.
  static TextStyle readout(BuildContext context, {Color? color, double size = 10.5}) {
    final p = AerisPalette.of(context);
    return TextStyle(
      fontFamilyFallback: T.mono,
      fontSize: size,
      fontWeight: FontWeight.w600,
      letterSpacing: 0.9,
      color: color ?? p.inkDim,
    );
  }
}
