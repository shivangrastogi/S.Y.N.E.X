import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../../brain/tier.dart';
import '../../design/theme.dart';
import '../../design/tokens.dart';
import '../../state/conversation.dart';
import '../tier_visuals.dart';

/// One turn of the transcript.
///
/// The assistant's replies carry a provenance rail down their leading edge and
/// a monospace readout beneath — the tier that answered, the skill if it was
/// on-device, and how long it took. That readout is the product: it is how the
/// user learns which questions are free and instant and which cost a round trip.
class MessageBubble extends StatelessWidget {
  const MessageBubble({super.key, required this.message});

  final Message message;

  /// An answer you cannot get out of the app is half an answer, and selecting
  /// canvas-rendered text on a phone is fiddly — so long-press copies it.
  Future<void> _copy(BuildContext context) async {
    if (message.pending || message.text.isEmpty) return;
    await Clipboard.setData(ClipboardData(text: message.text));
    if (!context.mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text('Copied', style: AerisTheme.readout(context, size: 11)),
        duration: const Duration(seconds: 1),
        behavior: SnackBarBehavior.floating,
        width: 120,
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final p = AerisPalette.of(context);

    if (message.fromUser) {
      return Semantics(
        label: 'You said',
        value: message.text,
        child: Align(
          alignment: Alignment.centerRight,
          child: Container(
            margin: const EdgeInsets.only(left: T.s6, bottom: T.s3),
            padding: const EdgeInsets.symmetric(
              horizontal: T.s4,
              vertical: T.s3 - 2,
            ),
            decoration: BoxDecoration(
              color: p.surfaceHi,
              borderRadius: BorderRadius.circular(T.radius),
            ),
            child: ExcludeSemantics(
              child: Text(message.text,
                  style: Theme.of(context).textTheme.bodyLarge),
            ),
          ),
        ),
      );
    }

    final tier = message.tier ?? Tier.none;
    final accent = tierColor(context, tier);

    return Semantics(
      // The provenance is rendered as a colour and a monospace readout, so a
      // screen reader would otherwise get the answer with none of the context
      // that makes it trustworthy.
      label: _semanticLabel(),
      value: message.pending ? null : message.text,
      liveRegion: message.pending,
      child: Align(
      alignment: Alignment.centerLeft,
      child: GestureDetector(
        onLongPress: () => _copy(context),
        child: Container(
        margin: const EdgeInsets.only(right: T.s6, bottom: T.s3),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisSize: MainAxisSize.min,
          children: [
            IntrinsicHeight(
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                mainAxisSize: MainAxisSize.min,
                children: [
                  Container(
                    width: T.railWidth,
                    decoration: BoxDecoration(
                      color: accent,
                      borderRadius: BorderRadius.circular(T.railWidth),
                    ),
                  ),
                  Flexible(
                    child: Container(
                      padding: const EdgeInsets.fromLTRB(T.s3, T.s3 - 2, T.s4, T.s3 - 2),
                      decoration: BoxDecoration(
                        color: p.surface,
                        borderRadius: const BorderRadius.only(
                          topRight: Radius.circular(T.radius),
                          bottomRight: Radius.circular(T.radius),
                          topLeft: Radius.circular(T.radiusSm),
                          bottomLeft: Radius.circular(T.radiusSm),
                        ),
                      ),
                      child: message.pending
                          ? _Thinking(color: p.inkDim)
                          : Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              mainAxisSize: MainAxisSize.min,
                              children: [
                                if (message.detail != null) ...[
                                  Text(
                                    message.detail!,
                                    style: AerisTheme.readout(context, size: 11),
                                  ),
                                  const SizedBox(height: T.s1),
                                ],
                                Text(
                                  message.text,
                                  style: Theme.of(context).textTheme.bodyLarge,
                                ),
                              ],
                            ),
                    ),
                  ),
                ],
              ),
            ),
            if (!message.pending) ...[
              const SizedBox(height: T.s1 + 1),
              Padding(
                padding: const EdgeInsets.only(left: T.s3),
                child: Text(
                  _readout(),
                  style: AerisTheme.readout(context, color: accent, size: 9.5),
                ),
              ),
            ],
          ],
        ),
        ),
      ),
      ),
    );
  }

  /// What a screen reader announces instead of the colour-coded rail.
  String _semanticLabel() {
    if (message.pending) return 'A.E.R.I.S is thinking';
    final tier = message.tier ?? Tier.none;
    final where = switch (tier) {
      Tier.device => 'answered on this phone',
      Tier.laptop => 'answered by the laptop',
      Tier.cloud => 'answered from the cloud',
      Tier.none => 'could not be answered',
    };
    final skill = message.skillName == null ? '' : ' by ${message.skillName}';
    return 'A.E.R.I.S, $where$skill';
  }

  String _readout() {
    final tier = (message.tier ?? Tier.none).label.toUpperCase();
    final parts = <String>[tier];
    if (message.skillName != null) parts.add(message.skillName!);
    if (message.elapsed != null) parts.add(formatLatency(message.elapsed!));
    return parts.join('  ·  ');
  }
}

/// Three dots that breathe while a tier is being tried. Held still when the
/// user has asked for reduced motion.
class _Thinking extends StatefulWidget {
  const _Thinking({required this.color});
  final Color color;

  @override
  State<_Thinking> createState() => _ThinkingState();
}

class _ThinkingState extends State<_Thinking>
    with SingleTickerProviderStateMixin {
  late final AnimationController _c = AnimationController(
    vsync: this,
    duration: const Duration(milliseconds: 1100),
  );

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    // MediaQuery rather than the binding's accessibilityFeatures: this one
    // rebuilds when the setting changes, and a test can supply it.
    final still = MediaQuery.of(context).disableAnimations;
    if (still && _c.isAnimating) {
      _c.stop();
    } else if (!still && !_c.isAnimating) {
      _c.repeat();
    }
  }

  @override
  void dispose() {
    _c.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      height: 20,
      child: AnimatedBuilder(
        animation: _c,
        builder: (context, _) {
          return Row(
            mainAxisSize: MainAxisSize.min,
            children: List.generate(3, (i) {
              final phase = (_c.value + i * 0.22) % 1.0;
              final lift = (phase < 0.5 ? phase : 1 - phase) * 2;
              return Padding(
                padding: const EdgeInsets.symmetric(horizontal: 2.5),
                child: Transform.translate(
                  offset: Offset(0, -lift),
                  child: Container(
                    width: 5,
                    height: 5,
                    decoration: BoxDecoration(
                      shape: BoxShape.circle,
                      color: widget.color.withValues(alpha: 0.45 + lift * 0.25),
                    ),
                  ),
                ),
              );
            }),
          );
        },
      ),
    );
  }
}
