import 'dart:async';
import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../tokens.dart';
import 'surfaces.dart';

enum BtnKind { primary, outline, danger, approve }

/// Chamfered button. Sentence-case label (R4).
class HudButton extends StatelessWidget {
  const HudButton({
    super.key,
    required this.label,
    required this.onPressed,
    this.kind = BtnKind.primary,
    this.icon,
    this.expand = false,
  });
  final String label;
  final VoidCallback? onPressed;
  final BtnKind kind;
  final IconData? icon;
  final bool expand;

  @override
  Widget build(BuildContext context) {
    final enabled = onPressed != null;
    final (Color fg, Color fill, Color border) = switch (kind) {
      BtnKind.primary => (C.bg, C.cyan, C.cyan),
      BtnKind.outline => (C.text1, Colors.transparent, C.hairline),
      BtnKind.danger => (C.red, C.red.withValues(alpha: 0.08), C.red.withValues(alpha: 0.6)),
      BtnKind.approve => (C.bg, C.amber, C.amber),
    };
    final child = Row(
      mainAxisSize: expand ? MainAxisSize.max : MainAxisSize.min,
      mainAxisAlignment: MainAxisAlignment.center,
      children: [
        if (icon != null) ...[Icon(icon, size: 18, color: fg), const SizedBox(width: S.sm)],
        Text(label,
            style: T.body.copyWith(
                fontSize: 14.5, fontWeight: FontWeight.w500, color: fg, height: 1.2)),
      ],
    );
    return Opacity(
      opacity: enabled ? 1 : 0.38,
      child: Material(
        color: fill,
        shape: ChamferBorder(cut: 8, side: BorderSide(color: border)),
        clipBehavior: Clip.antiAlias,
        child: InkWell(
          onTap: enabled
              ? () {
                  HapticFeedback.selectionClick();
                  onPressed!();
                }
              : null,
          splashColor: fg.withValues(alpha: 0.12),
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 14),
            child: child,
          ),
        ),
      ),
    );
  }
}

/// Plain icon button with a generous touch target.
class IconBtn extends StatelessWidget {
  const IconBtn(this.icon, {super.key, required this.onTap, this.tooltip, this.color = C.text2});
  final IconData icon;
  final VoidCallback onTap;
  final String? tooltip;
  final Color color;

  @override
  Widget build(BuildContext context) => IconButton(
        onPressed: onTap,
        tooltip: tooltip,
        icon: Icon(icon, color: color, size: 22),
        splashRadius: 22,
      );
}

/// Back arrow + screen title, the header of every pushed screen.
/// The arrow is nudged left so the title lines up with the page content.
class BackHeader extends StatelessWidget {
  const BackHeader(this.title, {super.key, this.trailing});
  final String title;
  final Widget? trailing;

  @override
  Widget build(BuildContext context) => Row(children: [
        Transform.translate(
          offset: const Offset(-12, 0),
          child: IconBtn(Icons.arrow_back_rounded, tooltip: 'Back', onTap: () => Navigator.of(context).maybePop()),
        ),
        Expanded(child: Text(title, style: T.title, overflow: TextOverflow.ellipsis)),
        ?trailing,
      ]);
}

/// Tiny uppercase mono section label (the only uppercase besides state word).
class SectionLabel extends StatelessWidget {
  const SectionLabel(this.text, {super.key, this.trailing});
  final String text;
  final Widget? trailing;

  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.only(bottom: S.sm),
        child: Row(children: [
          Text(text.toUpperCase(), style: T.label),
          const Spacer(),
          ?trailing,
        ]),
      );
}

/// Soft breathing status dot.
class StatusDot extends StatefulWidget {
  const StatusDot({super.key, this.color = C.mint, this.size = 7, this.pulse = true});
  final Color color;
  final double size;
  final bool pulse;

  @override
  State<StatusDot> createState() => _StatusDotState();
}

class _StatusDotState extends State<StatusDot> with SingleTickerProviderStateMixin {
  late final AnimationController _c =
      AnimationController(vsync: this, duration: const Duration(milliseconds: 2200));

  @override
  void initState() {
    super.initState();
    if (widget.pulse) _c.repeat(reverse: true);
  }

  @override
  void dispose() {
    _c.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => AnimatedBuilder(
        animation: _c,
        builder: (_, _) => Container(
          width: widget.size,
          height: widget.size,
          decoration: BoxDecoration(
            shape: BoxShape.circle,
            color: widget.color,
            boxShadow: [
              BoxShadow(
                  color: widget.color.withValues(alpha: 0.25 + 0.35 * _c.value),
                  blurRadius: 4 + 6 * _c.value),
            ],
          ),
        ),
      );
}

/// Small mono tag, e.g. which tier answered.
class Tag extends StatelessWidget {
  const Tag(this.text, {super.key, this.color = C.text3});
  final String text;
  final Color color;

  @override
  Widget build(BuildContext context) => Container(
        padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
        decoration: ShapeDecoration(
            shape: ChamferBorder(cut: 4, side: BorderSide(color: color.withValues(alpha: 0.45)))),
        child: Text(text.toUpperCase(),
            style: T.label.copyWith(color: color, fontSize: 9.5, letterSpacing: 1.2)),
      );
}

/// Text that "decodes" into place when [text] changes (R6: motion, not decor).
class DecodeText extends StatefulWidget {
  const DecodeText(this.text, {super.key, required this.style, this.duration = const Duration(milliseconds: 420)});
  final String text;
  final TextStyle style;
  final Duration duration;

  @override
  State<DecodeText> createState() => _DecodeTextState();
}

class _DecodeTextState extends State<DecodeText> {
  static const _glyphs = 'ABCDEFGHKLMNPRSTUVXZ0123456789/<>#';
  final _rnd = math.Random();
  late String _shown = widget.text;
  Timer? _timer;

  @override
  void didUpdateWidget(covariant DecodeText old) {
    super.didUpdateWidget(old);
    if (old.text != widget.text) _run();
  }

  void _run() {
    _timer?.cancel();
    final target = widget.text;
    final frames = (widget.duration.inMilliseconds / 30).round().clamp(4, 40);
    var f = 0;
    _timer = Timer.periodic(const Duration(milliseconds: 30), (t) {
      f++;
      final resolved = (target.length * f / frames).floor();
      if (f >= frames) {
        t.cancel();
        if (mounted) setState(() => _shown = target);
        return;
      }
      final b = StringBuffer(target.substring(0, resolved));
      for (var i = resolved; i < target.length; i++) {
        b.write(target[i] == ' ' ? ' ' : _glyphs[_rnd.nextInt(_glyphs.length)]);
      }
      if (mounted) setState(() => _shown = b.toString());
    });
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => Text(_shown, style: widget.style, maxLines: 1);
}

/// One row in a settings-style list.
class SettingRow extends StatelessWidget {
  const SettingRow({
    super.key,
    required this.title,
    this.subtitle,
    this.trailing,
    this.onTap,
    this.icon,
    this.titleColor = C.text1,
  });
  final String title;
  final String? subtitle;
  final Widget? trailing;
  final VoidCallback? onTap;
  final IconData? icon;
  final Color titleColor;

  @override
  Widget build(BuildContext context) => InkWell(
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: S.lg, vertical: 14),
          child: Row(children: [
            if (icon != null) ...[
              Icon(icon, size: 20, color: C.cyanDim),
              const SizedBox(width: S.md + 2),
            ],
            Expanded(
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Text(title, style: T.body.copyWith(color: titleColor, height: 1.3)),
                if (subtitle != null) ...[
                  const SizedBox(height: 2),
                  Text(subtitle!, style: T.small),
                ],
              ]),
            ),
            if (trailing != null) ...[const SizedBox(width: S.md), trailing!],
          ]),
        ),
      );
}

/// Groups rows in one panel with hairline separators.
class RowGroup extends StatelessWidget {
  const RowGroup({super.key, required this.children});
  final List<Widget> children;

  @override
  Widget build(BuildContext context) => Panel(
        padding: EdgeInsets.zero,
        child: Column(children: [
          for (var i = 0; i < children.length; i++) ...[
            if (i > 0) const Divider(height: 1, indent: S.lg, endIndent: S.lg),
            children[i],
          ],
        ]),
      );
}

/// Segmented choice, applied instantly.
class Segmented<V> extends StatelessWidget {
  const Segmented({super.key, required this.value, required this.options, required this.onChanged});
  final V value;
  final List<(V, String)> options;
  final ValueChanged<V> onChanged;

  @override
  Widget build(BuildContext context) => Container(
        decoration: const ShapeDecoration(shape: ChamferBorder()),
        padding: const EdgeInsets.all(3),
        child: Row(children: [
          for (final (v, label) in options)
            Expanded(
              child: GestureDetector(
                behavior: HitTestBehavior.opaque,
                onTap: () {
                  HapticFeedback.selectionClick();
                  onChanged(v);
                },
                child: AnimatedContainer(
                  duration: M.fast,
                  padding: const EdgeInsets.symmetric(vertical: 10),
                  decoration: ShapeDecoration(
                    color: v == value ? C.cyan.withValues(alpha: 0.12) : Colors.transparent,
                    shape: ChamferBorder(
                        cut: 5,
                        side: BorderSide(
                            color: v == value ? C.cyan.withValues(alpha: 0.6) : Colors.transparent)),
                  ),
                  alignment: Alignment.center,
                  child: Text(label,
                      style: T.small.copyWith(
                          color: v == value ? C.text1 : C.text2,
                          fontWeight: v == value ? FontWeight.w500 : FontWeight.w400)),
                ),
              ),
            ),
        ]),
      );
}

// ── feedback helpers (standard save protocol, see feedback_ui_style) ──

void showSaved(BuildContext context, [String msg = 'Saved']) {
  ScaffoldMessenger.of(context)
    ..hideCurrentSnackBar()
    ..showSnackBar(SnackBar(
      duration: const Duration(milliseconds: 1400),
      content: Row(children: [
        const Icon(Icons.check_rounded, color: C.mint, size: 18),
        const SizedBox(width: S.sm),
        Text(msg),
      ]),
    ));
}

void showUndo(BuildContext context, String msg, VoidCallback onUndo) {
  ScaffoldMessenger.of(context)
    ..hideCurrentSnackBar()
    ..showSnackBar(SnackBar(
      content: Text(msg),
      action: SnackBarAction(label: 'Undo', onPressed: onUndo),
    ));
}

Future<bool> confirm(BuildContext context,
    {required String title, required String body, String action = 'Delete', bool danger = true}) async {
  final r = await showDialog<bool>(
    context: context,
    builder: (c) => AlertDialog(
      title: Text(title),
      content: Text(body),
      actions: [
        TextButton(
            onPressed: () => Navigator.pop(c, false),
            child: Text('Cancel', style: T.body.copyWith(color: C.text2))),
        TextButton(
            onPressed: () => Navigator.pop(c, true),
            child: Text(action, style: T.body.copyWith(color: danger ? C.red : C.cyan))),
      ],
    ),
  );
  return r ?? false;
}
