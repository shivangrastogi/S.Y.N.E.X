import 'package:flutter/material.dart';

import '../../brain/tier.dart';
import '../../design/theme.dart';
import '../../design/tokens.dart';
import '../tier_visuals.dart';

/// The reach indicator: which tiers A.E.R.I.S can currently use, in the order
/// it will try them.
///
/// This is the app's honest status line. A dim pip is not a decoration — it
/// means questions that need that tier will not be answered right now.
class LinkStrip extends StatelessWidget {
  const LinkStrip({super.key, required this.reach});

  final Map<Tier, bool> reach;

  @override
  Widget build(BuildContext context) {
    final p = AerisPalette.of(context);
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: T.s4, vertical: T.s2),
      decoration: BoxDecoration(
        color: p.surface,
        border: Border(bottom: BorderSide(color: p.line)),
      ),
      child: Row(
        children: [
          for (final entry in reach.entries) ...[
            _Pip(tier: entry.key, live: entry.value),
            const SizedBox(width: T.s4),
          ],
          const Spacer(),
          Text('REACH', style: AerisTheme.readout(context, size: 9.5)),
        ],
      ),
    );
  }
}

class _Pip extends StatelessWidget {
  const _Pip({required this.tier, required this.live});

  final Tier tier;
  final bool live;

  @override
  Widget build(BuildContext context) {
    final p = AerisPalette.of(context);
    final color = live ? tierColor(context, tier) : p.inkDim;

    return Semantics(
      label: '${tier.label} ${live ? 'reachable' : 'not reachable'}',
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Container(
            width: 7,
            height: 7,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              color: live ? color : Colors.transparent,
              border: live ? null : Border.all(color: p.inkDim, width: 1.2),
            ),
          ),
          const SizedBox(width: T.s2 - 2),
          Text(
            tier.label.toUpperCase(),
            style: AerisTheme.readout(context, color: color, size: 9.5),
          ),
        ],
      ),
    );
  }
}
