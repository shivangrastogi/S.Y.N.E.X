import 'package:flutter/material.dart';

import '../brain/tier.dart';
import '../design/theme.dart';

/// The single place tier -> colour is decided, so the rail on a bubble and the
/// pip in the status strip can never disagree about what "laptop" looks like.
Color tierColor(BuildContext context, Tier tier) {
  final p = AerisPalette.of(context);
  return switch (tier) {
    Tier.device => p.tierDevice,
    Tier.laptop => p.tierLaptop,
    Tier.cloud => p.tierCloud,
    Tier.none => p.inkDim,
  };
}

IconData tierIcon(Tier tier) => switch (tier) {
      Tier.device => Icons.smartphone,
      Tier.laptop => Icons.laptop_mac,
      Tier.cloud => Icons.cloud_outlined,
      Tier.none => Icons.help_outline,
    };

/// Latency, rendered at the precision a person can act on: whole milliseconds
/// under a second, one decimal of a second beyond that.
String formatLatency(Duration d) {
  final ms = d.inMicroseconds / 1000;
  if (ms < 1) return '<1 ms';
  if (ms < 1000) return '${ms.round()} ms';
  return '${(ms / 1000).toStringAsFixed(1)} s';
}
