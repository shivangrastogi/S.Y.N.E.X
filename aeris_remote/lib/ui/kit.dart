// Aurora Pro building blocks shared by every screen: page scaffold, grouped
// settings sections and rows, status badges, and the standard save
// patterns (toggles apply instantly with a confirmation; forms have an
// explicit Save that is enabled only when something changed, and leaving
// with unsaved edits asks first).
import 'package:flutter/material.dart';

import 'theme.dart';

/// A settings/detail page: back button, title, optional actions, scrolling
/// body with standard padding.
class PageScaffold extends StatelessWidget {
  final String title;
  final List<Widget> children;
  final List<Widget>? actions;
  final Widget? bottom;
  final Future<void> Function()? onRefresh;
  const PageScaffold({super.key, required this.title, required this.children, this.actions, this.bottom, this.onRefresh});

  @override
  Widget build(BuildContext context) {
    final list = ListView(
      padding: const EdgeInsets.fromLTRB(16, 4, 16, 32),
      children: children,
    );
    return Scaffold(
      appBar: AppBar(title: Text(title), actions: actions),
      body: onRefresh == null ? list : RefreshIndicator(onRefresh: onRefresh!, child: list),
      bottomNavigationBar: bottom,
    );
  }
}

/// A titled group of rows in one rounded panel.
class Section extends StatelessWidget {
  final String? title;
  final List<Widget> children;
  final String? footer;
  const Section({super.key, this.title, required this.children, this.footer});

  @override
  Widget build(BuildContext context) {
    final rows = <Widget>[];
    for (var i = 0; i < children.length; i++) {
      if (i > 0) rows.add(const Divider(indent: 16, endIndent: 16));
      rows.add(children[i]);
    }
    return Padding(
      padding: const EdgeInsets.only(top: 18),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        if (title != null) Padding(padding: const EdgeInsets.only(left: 4, bottom: 8), child: A.label(title!)),
        Container(
          clipBehavior: Clip.antiAlias,
          decoration: BoxDecoration(
            color: A.panel,
            borderRadius: BorderRadius.circular(A.radius),
            border: Border.all(color: A.line),
          ),
          child: Column(children: rows),
        ),
        if (footer != null)
          Padding(
            padding: const EdgeInsets.fromLTRB(4, 8, 4, 0),
            child: Text(footer!, style: const TextStyle(color: A.faint, fontSize: 12, height: 1.45)),
          ),
      ]),
    );
  }
}

/// One settings row. Navigation rows show [value] + a chevron; pass
/// [trailing] for a switch, button or badge instead.
class SettingsTile extends StatelessWidget {
  final IconData? icon;
  final String title;
  final String? subtitle;
  final String? value;
  final Color? valueColor;
  final Widget? trailing;
  final VoidCallback? onTap;
  final bool chevron;
  final bool destructive;
  const SettingsTile({
    super.key,
    this.icon,
    required this.title,
    this.subtitle,
    this.value,
    this.valueColor,
    this.trailing,
    this.onTap,
    this.chevron = true,
    this.destructive = false,
  });

  @override
  Widget build(BuildContext context) {
    return Material(
      color: Colors.transparent,
      child: InkWell(
        onTap: onTap,
        child: ConstrainedBox(
          constraints: const BoxConstraints(minHeight: 56),
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
            child: Row(children: [
              if (icon != null) ...[
                Icon(icon, size: 20, color: destructive ? A.hot : A.muted),
                const SizedBox(width: 14),
              ],
              Expanded(
                child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  Text(title, style: TextStyle(color: destructive ? A.hot : A.text, fontSize: 14.5)),
                  if (subtitle != null)
                    Padding(
                      padding: const EdgeInsets.only(top: 3),
                      child: Text(subtitle!, style: const TextStyle(color: A.muted, fontSize: 12, height: 1.4)),
                    ),
                ]),
              ),
              if (value != null)
                Padding(
                  padding: const EdgeInsets.only(left: 10),
                  child: Text(value!, style: TextStyle(color: valueColor ?? A.muted, fontSize: 13)),
                ),
              if (trailing != null) Padding(padding: const EdgeInsets.only(left: 10), child: trailing!),
              if (trailing == null && onTap != null && chevron)
                const Padding(
                  padding: EdgeInsets.only(left: 6),
                  child: Icon(Icons.chevron_right, color: A.faint, size: 20),
                ),
            ]),
          ),
        ),
      ),
    );
  }
}

/// A switch row that applies immediately and confirms with a snackbar.
class SwitchTile extends StatelessWidget {
  final IconData? icon;
  final String title;
  final String? subtitle;
  final bool value;
  final bool busy;
  final ValueChanged<bool>? onChanged;
  const SwitchTile({super.key, this.icon, required this.title, this.subtitle, required this.value, this.onChanged, this.busy = false});

  @override
  Widget build(BuildContext context) => SettingsTile(
        icon: icon,
        title: title,
        subtitle: subtitle,
        onTap: onChanged == null || busy ? null : () => onChanged!(!value),
        trailing: busy
            ? const SizedBox(width: 22, height: 22, child: CircularProgressIndicator(strokeWidth: 2))
            : Switch(value: value, onChanged: onChanged),
      );
}

enum BadgeTone { ok, warn, bad, neutral, accent }

/// Small status chip ("Connected", "2 to fix", "Off").
class StatusBadge extends StatelessWidget {
  final String text;
  final BadgeTone tone;
  const StatusBadge(this.text, {super.key, this.tone = BadgeTone.neutral});

  @override
  Widget build(BuildContext context) {
    final c = switch (tone) {
      BadgeTone.ok => A.ok,
      BadgeTone.warn => A.warn,
      BadgeTone.bad => A.hot,
      BadgeTone.accent => A.accent,
      BadgeTone.neutral => A.muted,
    };
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
      decoration: BoxDecoration(color: c.withValues(alpha: 0.12), borderRadius: BorderRadius.circular(6)),
      child: Text(text, style: TextStyle(color: c, fontSize: 11.5, fontWeight: FontWeight.w500)),
    );
  }
}

/// Standard confirmation after a setting is applied.
void showSaved(BuildContext context, String message) {
  final m = ScaffoldMessenger.of(context);
  m.hideCurrentSnackBar();
  m.showSnackBar(SnackBar(
    content: Row(children: [
      const Icon(Icons.check_circle, color: A.ok, size: 18),
      const SizedBox(width: 10),
      Expanded(child: Text(message)),
    ]),
    duration: const Duration(seconds: 2),
  ));
}

void showError(BuildContext context, String message) {
  final m = ScaffoldMessenger.of(context);
  m.hideCurrentSnackBar();
  m.showSnackBar(SnackBar(
    content: Row(children: [
      const Icon(Icons.error_outline, color: A.hot, size: 18),
      const SizedBox(width: 10),
      Expanded(child: Text(message)),
    ]),
  ));
}

/// Yes/no dialog for destructive or irreversible actions.
Future<bool> confirm(BuildContext context,
    {required String title, required String body, String action = 'Confirm', bool destructive = false}) async {
  final ok = await showDialog<bool>(
    context: context,
    builder: (c) => AlertDialog(
      title: Text(title),
      content: Text(body),
      actions: [
        TextButton(onPressed: () => Navigator.pop(c, false), child: const Text('Cancel', style: TextStyle(color: A.muted))),
        TextButton(
          onPressed: () => Navigator.pop(c, true),
          child: Text(action, style: TextStyle(color: destructive ? A.hot : A.accent)),
        ),
      ],
    ),
  );
  return ok ?? false;
}

/// Wraps a form page: guards the back gesture while [dirty] ("Discard
/// changes?"), and shows a sticky "unsaved changes" bar with Discard/Save.
class UnsavedChangesGuard extends StatelessWidget {
  final bool dirty;
  final bool saving;
  final VoidCallback onSave;
  final VoidCallback onDiscard;
  final Widget child;
  const UnsavedChangesGuard({
    super.key,
    required this.dirty,
    required this.onSave,
    required this.onDiscard,
    required this.child,
    this.saving = false,
  });

  @override
  Widget build(BuildContext context) {
    return PopScope(
      canPop: !dirty,
      onPopInvokedWithResult: (didPop, _) async {
        if (didPop) return;
        final leave = await confirm(context,
            title: 'Discard changes?', body: 'You have edits that aren\'t saved yet.', action: 'Discard', destructive: true);
        if (leave && context.mounted) {
          onDiscard();
          Navigator.of(context).pop();
        }
      },
      child: Stack(children: [
        child,
        Positioned(
          left: 16,
          right: 16,
          bottom: 16,
          child: SafeArea(
            top: false,
            child: AnimatedSlide(
              offset: dirty ? Offset.zero : const Offset(0, 2),
              duration: const Duration(milliseconds: 220),
              curve: Curves.easeOutCubic,
              child: AnimatedOpacity(
                opacity: dirty ? 1 : 0,
                duration: const Duration(milliseconds: 180),
                child: Material(
                  color: A.panelHi,
                  elevation: 8,
                  shadowColor: Colors.black,
                  shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(14), side: const BorderSide(color: A.line)),
                  child: Padding(
                    padding: const EdgeInsets.fromLTRB(16, 8, 8, 8),
                    child: Row(children: [
                      const Expanded(child: Text('Unsaved changes', style: TextStyle(color: A.text, fontSize: 13.5))),
                      TextButton(
                          onPressed: saving ? null : onDiscard,
                          child: const Text('Discard', style: TextStyle(color: A.muted))),
                      const SizedBox(width: 4),
                      FilledButton(
                        style: FilledButton.styleFrom(backgroundColor: A.accent, minimumSize: const Size(80, 40)),
                        onPressed: saving ? null : onSave,
                        child: saving
                            ? const SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2, color: A.onLight))
                            : const Text('Save'),
                      ),
                    ]),
                  ),
                ),
              ),
            ),
          ),
        ),
      ]),
    );
  }
}

/// Labelled 3-way choice that applies on tap.
class ChoiceRow<T> extends StatelessWidget {
  final List<(T, String)> options;
  final T value;
  final ValueChanged<T> onChanged;
  const ChoiceRow({super.key, required this.options, required this.value, required this.onChanged});

  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.all(12),
        child: SegmentedButton<T>(
          showSelectedIcon: false,
          segments: [for (final (v, l) in options) ButtonSegment(value: v, label: Text(l))],
          selected: {value},
          onSelectionChanged: (s) => onChanged(s.first),
        ),
      );
}
