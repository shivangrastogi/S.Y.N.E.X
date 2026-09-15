import 'package:flutter/widgets.dart';

/// Design tokens for A.E.R.I.S Mobile.
///
/// The organising idea: **provenance is the interface**. Every answer comes
/// from one of three tiers, and each tier owns a hue that means something —
/// brass for the phone (immediate, in your hand), cyan for the laptop across
/// the room, violet for the cloud. Those three are the only saturated colors
/// in the app; everything else is blue-steel neutral so they read instantly.
class T {
  const T._();

  // ---- neutrals, dark (the default: assistants get used at night) ----
  static const groundDark = Color(0xFF12171D);
  static const surfaceDark = Color(0xFF1A2129);
  static const surfaceHiDark = Color(0xFF232C36);
  static const lineDark = Color(0xFF2E3A45);
  static const inkDark = Color(0xFFE4EAF0);
  static const inkDimDark = Color(0xFF94A3B1);

  // ---- neutrals, light ----
  static const groundLight = Color(0xFFF2F4F7);
  static const surfaceLight = Color(0xFFFFFFFF);
  static const surfaceHiLight = Color(0xFFE9EDF2);
  static const lineLight = Color(0xFFD3DBE4);
  static const inkLight = Color(0xFF131A21);
  static const inkDimLight = Color(0xFF5C6875);

  // ---- tier hues: semantic, not decorative ----
  static const tierDevice = Color(0xFFE0A458); // brass  — answered on-device
  static const tierLaptop = Color(0xFF4FB6C4); // cyan   — answered by laptop
  static const tierCloud = Color(0xFFA98BD9); // violet — answered by cloud

  // Light-theme variants: same hues, darkened enough to hold contrast on paper.
  static const tierDeviceLight = Color(0xFFA96D14);
  static const tierLaptopLight = Color(0xFF12707E);
  static const tierCloudLight = Color(0xFF6A4BA5);

  static const danger = Color(0xFFE2685F);

  // ---- type ----
  // No bundled fonts: the app leans on what the platform already has, with a
  // monospace stack reserved for instrument readouts (tier, latency, clock).
  static const sans = <String>['Segoe UI', 'Roboto', 'Helvetica', 'Arial'];
  static const mono = <String>[
    'Cascadia Mono',
    'Consolas',
    'Roboto Mono',
    'monospace',
  ];

  // ---- spacing: a 4pt scale, used everywhere ----
  static const s1 = 4.0;
  static const s2 = 8.0;
  static const s3 = 12.0;
  static const s4 = 16.0;
  static const s5 = 24.0;
  static const s6 = 32.0;

  static const radius = 14.0;
  static const radiusSm = 8.0;

  /// Width of the provenance rail down the side of an assistant reply.
  static const railWidth = 3.0;
}
