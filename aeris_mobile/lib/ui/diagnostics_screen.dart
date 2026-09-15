import 'package:flutter/material.dart';

import '../core/logger.dart';
import '../design/theme.dart';
import '../design/tokens.dart';

/// What the app has been doing, from the in-memory ring buffer.
///
/// An assistant fails quietly by nature — a skill declines, a tier is
/// unreachable, a permission was refused — and none of that belongs in the
/// transcript. This is where it goes instead, so "it just said it couldn't"
/// has an answer without attaching a debugger.
class DiagnosticsScreen extends StatefulWidget {
  const DiagnosticsScreen({
    super.key,
    required this.log,
    required this.skillCount,
    required this.messageCount,
  });

  final AerisLog log;
  final int skillCount;
  final int messageCount;

  @override
  State<DiagnosticsScreen> createState() => _DiagnosticsScreenState();
}

class _DiagnosticsScreenState extends State<DiagnosticsScreen> {
  bool _problemsOnly = false;

  @override
  void initState() {
    super.initState();
    widget.log.addListener(_onLog);
  }

  @override
  void dispose() {
    widget.log.removeListener(_onLog);
    super.dispose();
  }

  void _onLog() {
    if (mounted) setState(() {});
  }

  Color _levelColor(BuildContext context, LogLevel level) {
    final p = AerisPalette.of(context);
    return switch (level) {
      LogLevel.debug => p.inkDim,
      LogLevel.info => p.tierLaptop,
      LogLevel.warn => p.tierDevice,
      LogLevel.error => p.danger,
    };
  }

  @override
  Widget build(BuildContext context) {
    final p = AerisPalette.of(context);
    final all = widget.log.entries;
    final shown = _problemsOnly
        ? all
            .where((e) => e.level == LogLevel.warn || e.level == LogLevel.error)
            .toList()
        : all;
    final problems = all
        .where((e) => e.level == LogLevel.warn || e.level == LogLevel.error)
        .length;

    return Scaffold(
      appBar: AppBar(
        backgroundColor: p.surface,
        elevation: 0,
        title: Text(
          'DIAGNOSTICS',
          style: AerisTheme.readout(context, color: p.ink, size: 13),
        ),
        actions: [
          if (all.isNotEmpty)
            TextButton(
              onPressed: () {
                widget.log.clear();
                setState(() => _problemsOnly = false);
              },
              child: Text('Clear', style: AerisTheme.readout(context, size: 11)),
            ),
        ],
      ),
      body: Column(
        children: [
          _Stats(
            skills: widget.skillCount,
            messages: widget.messageCount,
            events: all.length,
            problems: problems,
          ),
          Container(
            padding: const EdgeInsets.symmetric(
              horizontal: T.s4,
              vertical: T.s2,
            ),
            decoration: BoxDecoration(
              border: Border(bottom: BorderSide(color: p.line)),
            ),
            child: Row(
              children: [
                Text('ACTIVITY', style: AerisTheme.readout(context, size: 9.5)),
                const Spacer(),
                Semantics(
                  label: 'Show warnings and errors only',
                  child: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Text(
                        'PROBLEMS ONLY',
                        style: AerisTheme.readout(context, size: 9.5),
                      ),
                      const SizedBox(width: T.s2),
                      Switch(
                        value: _problemsOnly,
                        onChanged: (v) => setState(() => _problemsOnly = v),
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),
          Expanded(
            child: shown.isEmpty
                ? Center(
                    child: Padding(
                      padding: const EdgeInsets.all(T.s5),
                      child: Text(
                        _problemsOnly
                            ? 'Nothing has gone wrong.'
                            : 'Nothing logged yet. Ask A.E.R.I.S something.',
                        textAlign: TextAlign.center,
                        style: Theme.of(context).textTheme.bodySmall,
                      ),
                    ),
                  )
                : ListView.builder(
                    padding: const EdgeInsets.symmetric(vertical: T.s2),
                    itemCount: shown.length,
                    itemBuilder: (context, i) {
                      final e = shown[i];
                      return Padding(
                        padding: const EdgeInsets.symmetric(
                          horizontal: T.s4,
                          vertical: T.s1 + 1,
                        ),
                        child: Row(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(e.stamp,
                                style: AerisTheme.readout(context, size: 10)),
                            const SizedBox(width: T.s2),
                            SizedBox(
                              width: 42,
                              child: Text(
                                e.level.name.toUpperCase(),
                                style: AerisTheme.readout(
                                  context,
                                  color: _levelColor(context, e.level),
                                  size: 10,
                                ),
                              ),
                            ),
                            const SizedBox(width: T.s1),
                            Expanded(
                              child: Text.rich(
                                TextSpan(children: [
                                  TextSpan(
                                    text: '${e.tag}  ',
                                    style: AerisTheme.readout(context, size: 10),
                                  ),
                                  TextSpan(
                                    text: e.message,
                                    style:
                                        Theme.of(context).textTheme.bodySmall,
                                  ),
                                ]),
                              ),
                            ),
                          ],
                        ),
                      );
                    },
                  ),
          ),
        ],
      ),
    );
  }
}

class _Stats extends StatelessWidget {
  const _Stats({
    required this.skills,
    required this.messages,
    required this.events,
    required this.problems,
  });

  final int skills;
  final int messages;
  final int events;
  final int problems;

  @override
  Widget build(BuildContext context) {
    final p = AerisPalette.of(context);
    return Container(
      padding: const EdgeInsets.all(T.s4),
      decoration: BoxDecoration(
        color: p.surface,
        border: Border(bottom: BorderSide(color: p.line)),
      ),
      child: Row(
        children: [
          _Stat(label: 'SKILLS', value: '$skills'),
          _Stat(label: 'MESSAGES', value: '$messages'),
          _Stat(label: 'EVENTS', value: '$events'),
          _Stat(
            label: 'PROBLEMS',
            value: '$problems',
            color: problems > 0 ? p.tierDevice : null,
          ),
        ],
      ),
    );
  }
}

class _Stat extends StatelessWidget {
  const _Stat({required this.label, required this.value, this.color});

  final String label;
  final String value;
  final Color? color;

  @override
  Widget build(BuildContext context) {
    final p = AerisPalette.of(context);
    return Expanded(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(label, style: AerisTheme.readout(context, size: 9.5)),
          const SizedBox(height: 2),
          Text(
            value,
            style: TextStyle(
              fontFamilyFallback: T.mono,
              fontSize: 20,
              fontWeight: FontWeight.w600,
              fontFeatures: const [FontFeature.tabularFigures()],
              color: color ?? p.ink,
            ),
          ),
        ],
      ),
    );
  }
}
