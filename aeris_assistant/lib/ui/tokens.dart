import 'package:flutter/material.dart';

/// Colour tokens. One accent (cyan); amber/red/mint carry meaning only.
/// See docs/DESIGN.md before adding anything here.
abstract final class C {
  static const bg = Color(0xFF04070B);
  static const haze = Color(0xFF0A2530);
  static const surface = Color(0xFF0A1117);
  static const surfaceHi = Color(0xFF0E1820);
  static const hairline = Color(0x1F38D9FF); // cyan @ 12%
  static const hairlineSoft = Color(0x1238D9FF); // cyan @ 7%

  static const text1 = Color(0xFFDDF4FF);
  static const text2 = Color(0xFF7FA6B8);
  static const text3 = Color(0xFF4A6878);

  static const cyan = Color(0xFF38D9FF);
  static const cyanDim = Color(0xFF167A94);
  static const cyanHot = Color(0xFFCFF6FF);

  static const mint = Color(0xFF5EE6B5); // done / ready
  static const amber = Color(0xFFFFB454); // needs your OK
  static const red = Color(0xFFFF4D5E); // stop / error
}

/// Spacing on an 8pt grid.
abstract final class S {
  static const xs = 4.0;
  static const sm = 8.0;
  static const md = 12.0;
  static const lg = 16.0;
  static const side = 20.0;
  static const xl = 24.0;
  static const xxl = 32.0;
  static const huge = 48.0;
}

/// Text styles. Sora = anything a human reads. Oxanium = wordmark + voice
/// state word only. JetBrains Mono = real numbers and tiny section labels.
abstract final class T {
  static const _sora = 'Sora';
  static const _ox = 'Oxanium';
  static const _mono = 'JetBrainsMono';

  static List<FontVariation> _w(double w) => [FontVariation('wght', w)];

  static const title = TextStyle(
      fontFamily: _sora,
      fontSize: 24,
      fontWeight: FontWeight.w500,
      height: 1.25,
      letterSpacing: -0.3,
      color: C.text1);
  static const heading = TextStyle(
      fontFamily: _sora,
      fontSize: 18,
      fontWeight: FontWeight.w500,
      height: 1.3,
      color: C.text1);
  static const body = TextStyle(
      fontFamily: _sora,
      fontSize: 15,
      fontWeight: FontWeight.w400,
      height: 1.5,
      color: C.text1);
  static const bodyDim = TextStyle(
      fontFamily: _sora,
      fontSize: 14,
      fontWeight: FontWeight.w400,
      height: 1.45,
      color: C.text2);
  static const small = TextStyle(
      fontFamily: _sora,
      fontSize: 12.5,
      fontWeight: FontWeight.w400,
      height: 1.4,
      color: C.text2);
  static const transcript = TextStyle(
      fontFamily: _sora,
      fontSize: 22,
      fontWeight: FontWeight.w300,
      height: 1.4,
      letterSpacing: -0.2,
      color: C.text1);

  static final wordmark = TextStyle(
      fontFamily: _ox,
      fontSize: 15,
      fontVariations: _w(600),
      letterSpacing: 6,
      color: C.text1);
  static final stateWord = TextStyle(
      fontFamily: _ox,
      fontSize: 13,
      fontVariations: _w(600),
      letterSpacing: 4,
      color: C.cyan);
  static final display = TextStyle(
      fontFamily: _ox,
      fontSize: 34,
      fontVariations: _w(500),
      letterSpacing: 10,
      color: C.text1);

  static final label = TextStyle(
      fontFamily: _mono,
      fontSize: 10.5,
      fontVariations: _w(500),
      letterSpacing: 1.6,
      color: C.text3);
  static final mono = TextStyle(
      fontFamily: _mono,
      fontSize: 12,
      fontVariations: _w(450),
      letterSpacing: 0.4,
      color: C.text2);
  static final monoStrong = TextStyle(
      fontFamily: _mono,
      fontSize: 13,
      fontVariations: _w(600),
      letterSpacing: 0.4,
      color: C.text1);
}

/// Motion constants (see docs/STITCH_PROMPTS.md §5).
abstract final class M {
  static const fast = Duration(milliseconds: 160);
  static const base = Duration(milliseconds: 260);
  static const slow = Duration(milliseconds: 420);
  static const stagger = Duration(milliseconds: 40);
  static const ease = Curves.easeOutCubic;
}
