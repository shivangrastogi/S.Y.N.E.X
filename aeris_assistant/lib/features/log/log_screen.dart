import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';

import '../../app/scope.dart';
import '../../brain/executor.dart';
import '../../core/models.dart';
import '../../ui/kit/controls.dart';
import '../../ui/kit/surfaces.dart';
import '../../ui/tokens.dart';

/// Everything AERIS did, newest first. Real numbers only (DESIGN R1).
class LogScreen extends StatelessWidget {
  const LogScreen({super.key});

  static IconData iconFor(String tool) => switch (tool) {
        'time' => Icons.schedule_rounded,
        'date' => Icons.calendar_today_outlined,
        'battery' => Icons.battery_5_bar_rounded,
        'alarm' => Icons.alarm_rounded,
        'timer' => Icons.timer_outlined,
        'torch' => Icons.flashlight_on_outlined,
        'call' => Icons.call_outlined,
        'message' => Icons.chat_bubble_outline_rounded,
        'open' => Icons.apps_rounded,
        'search' => Icons.travel_explore_rounded,
        'remember' || 'recall' => Icons.bookmark_border_rounded,
        'math' => Icons.calculate_outlined,
        'protocol' => Icons.account_tree_outlined,
        _ => Icons.forum_outlined,
      };

  @override
  Widget build(BuildContext context) {
    final store = context.store;
    return SafeArea(
      bottom: false,
      child: ListenableBuilder(
        listenable: store,
        builder: (context, _) {
          final items = store.activity;
          final st = store.stats();
          return CustomScrollView(slivers: [
            SliverToBoxAdapter(
              child: _Header(
                title: 'Log',
                subtitle: items.isEmpty
                    ? 'What AERIS does shows up here.'
                    : '${st.today} today · ${items.length} total${st.avgMs > 0 ? ' · ${st.avgMs} ms avg' : ''}',
                trailing: items.isEmpty
                    ? null
                    : IconBtn(Icons.delete_sweep_outlined, tooltip: 'Clear log', onTap: () async {
                        if (await confirm(context,
                            title: 'Clear the log?', body: 'This removes all ${items.length} entries from this phone.', action: 'Clear')) {
                          store.clearActivity();
                          if (context.mounted) showSaved(context, 'Log cleared');
                        }
                      }),
              ),
            ),
            if (items.isEmpty)
              const SliverFillRemaining(hasScrollBody: false, child: _Empty())
            else
              SliverPadding(
                padding: const EdgeInsets.fromLTRB(S.side, 0, S.side, S.xxl),
                sliver: SliverList.builder(
                  itemCount: items.length,
                  itemBuilder: (context, i) {
                    final e = items[i];
                    final newDay = i == 0 || !_sameDay(items[i - 1].at, e.at);
                    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                      if (newDay) Padding(
                        padding: EdgeInsets.only(top: i == 0 ? 0 : S.xl, bottom: S.sm),
                        child: Text(_dayLabel(e.at).toUpperCase(), style: T.label),
                      ),
                      _Row(e).animate().fadeIn(duration: M.base, delay: M.stagger * (i < 12 ? i : 12)),
                    ]);
                  },
                ),
              ),
          ]);
        },
      ),
    );
  }

  static bool _sameDay(DateTime a, DateTime b) => a.year == b.year && a.month == b.month && a.day == b.day;

  static String _dayLabel(DateTime d) {
    final now = DateTime.now();
    if (_sameDay(d, now)) return 'Today';
    if (_sameDay(d, now.subtract(const Duration(days: 1)))) return 'Yesterday';
    const m = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
    return '${d.day} ${m[d.month - 1]}';
  }
}

class _Header extends StatelessWidget {
  const _Header({super.key, required this.title, required this.subtitle, this.trailing});
  final String title;
  final String subtitle;
  final Widget? trailing;

  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.fromLTRB(S.side, S.xl, S.sm, S.xl),
        child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Expanded(
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text(title, style: T.title),
              const SizedBox(height: S.xs),
              Text(subtitle, style: T.bodyDim),
            ]),
          ),
          ?trailing,
        ]),
      );
}

/// Shared page header (Memory / Protocols use it too).
class PageHeader extends _Header {
  const PageHeader({super.key, required super.title, required super.subtitle, super.trailing});
}

class _Row extends StatelessWidget {
  const _Row(this.e);
  final ActivityEntry e;

  @override
  Widget build(BuildContext context) {
    final color = switch (e.status) {
      TurnStatus.ok => C.cyan,
      TurnStatus.failed => C.red,
      TurnStatus.cancelled => C.text3,
      TurnStatus.unknown => C.amber,
    };
    return Padding(
      padding: const EdgeInsets.only(bottom: S.sm),
      child: Panel(
        onTap: () => _detail(context, e),
        padding: const EdgeInsets.symmetric(horizontal: S.lg, vertical: 14),
        child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Padding(
            padding: const EdgeInsets.only(top: 2),
            child: Icon(LogScreen.iconFor(e.tool), size: 19, color: color),
          ),
          const SizedBox(width: S.md + 2),
          Expanded(
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text(e.reply, style: T.body.copyWith(fontSize: 14.5, height: 1.35), maxLines: 2, overflow: TextOverflow.ellipsis),
              if (e.said.isNotEmpty) ...[
                const SizedBox(height: 3),
                Text('${e.typed ? 'Typed' : 'You said'}: ${e.said}',
                    style: T.small, maxLines: 1, overflow: TextOverflow.ellipsis),
              ],
            ]),
          ),
          const SizedBox(width: S.md),
          Text(_hm(e.at), style: T.mono.copyWith(fontSize: 11, color: C.text3)),
        ]),
      ),
    );
  }

  static String _hm(DateTime t) => '${t.hour.toString().padLeft(2, '0')}:${t.minute.toString().padLeft(2, '0')}';

  static void _detail(BuildContext context, ActivityEntry e) {
    showModalBottomSheet<void>(
      context: context,
      showDragHandle: true,
      isScrollControlled: true,
      builder: (c) => SafeArea(
        child: Padding(
          padding: const EdgeInsets.fromLTRB(S.side, 0, S.side, S.xl),
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, mainAxisSize: MainAxisSize.min, children: [
            Text(toolLabel(e.tool), style: T.heading),
            const SizedBox(height: S.xl),
            if (e.said.isNotEmpty) ...[
              Text(e.typed ? 'YOU TYPED' : 'YOU SAID', style: T.label),
              const SizedBox(height: S.xs),
              Text('“${e.said}”', style: T.body),
              const SizedBox(height: S.lg),
            ],
            Text('HOW AERIS UNDERSTOOD IT', style: T.label),
            const SizedBox(height: S.xs),
            Container(
              width: double.infinity,
              padding: const EdgeInsets.all(S.md),
              decoration: const ShapeDecoration(color: C.bg, shape: ChamferBorder()),
              child: Text(
                [
                  'action  ${e.tool}',
                  for (final a in e.args.entries) '${a.key.padRight(7)} ${a.value}',
                ].join('\n'),
                style: T.mono.copyWith(color: C.text1, height: 1.6),
              ),
            ),
            const SizedBox(height: S.lg),
            Text('RESULT', style: T.label),
            const SizedBox(height: S.xs),
            Text(e.reply, style: T.body),
            const SizedBox(height: S.lg),
            Row(children: [
              const Icon(Icons.phone_android_rounded, size: 16, color: C.text3),
              const SizedBox(width: 6),
              Text('Answered on this phone in ${e.latencyMs} ms', style: T.small),
            ]),
            const SizedBox(height: S.xl),
            if (e.said.isNotEmpty)
              HudButton(
                label: 'Run again',
                icon: Icons.replay_rounded,
                kind: BtnKind.outline,
                onPressed: () {
                  Navigator.pop(c);
                  context.session.submitText(e.said);
                },
              ),
          ]),
        ),
      ),
    );
  }
}

class _Empty extends StatelessWidget {
  const _Empty();

  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.all(S.huge),
        child: Column(mainAxisAlignment: MainAxisAlignment.center, children: [
          Icon(Icons.receipt_long_outlined, size: 40, color: C.text3.withValues(alpha: 0.6)),
          const SizedBox(height: S.lg),
          const Text('Nothing yet.', style: T.heading),
          const SizedBox(height: S.xs),
          const Text('Ask AERIS something and it will appear here.', style: T.bodyDim, textAlign: TextAlign.center),
        ]),
      );
}
