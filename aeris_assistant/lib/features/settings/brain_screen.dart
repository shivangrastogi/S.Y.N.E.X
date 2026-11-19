// Settings → Brain: status of the on-device LLM, its mode, a "try it" box and
// the recent decision log. Built only from the UI kit (lib/ui/kit/).
import 'dart:io';

import 'package:flutter/material.dart';

import '../../app/scope.dart';
import '../../brain/llm/brain.dart';
import '../../ui/kit/controls.dart';
import '../../ui/kit/surfaces.dart';
import '../../ui/tokens.dart';

/// The row in Settings that opens [BrainScreen] and shows the brain's state.
class BrainSettingsRow extends StatelessWidget {
  const BrainSettingsRow({super.key});

  @override
  Widget build(BuildContext context) {
    final brain = context.session.brain;
    if (brain == null) {
      return const SettingRow(icon: Icons.psychology_outlined, title: 'On-device brain', subtitle: 'Not available in this build');
    }
    return ListenableBuilder(
      listenable: Listenable.merge([brain.status, brain.mode]),
      builder: (context, _) => SettingRow(
        icon: Icons.psychology_outlined,
        title: 'On-device brain',
        subtitle: _statusLine(brain, brain.status.value),
        trailing: const Icon(Icons.chevron_right_rounded, color: C.text3),
        onTap: () => Navigator.of(context).push(MaterialPageRoute<void>(builder: (_) => const BrainScreen())),
      ),
    );
  }
}

String _statusLine(AerisBrain brain, BrainStatus status) {
  if (brain.mode.value == BrainMode.off) return 'Off — rules only';
  return switch (status) {
    BrainStatus.noModel => 'No model file yet — see inside',
    BrainStatus.idle => 'Ready to load · ${_modelName(brain.modelPath)}',
    BrainStatus.loading => 'Loading…',
    BrainStatus.ready => 'Loaded · ${_modelName(brain.modelPath)}',
    BrainStatus.error => 'Error — tap for details',
  };
}

String _modelName(String? path) => path == null ? '—' : path.split(RegExp(r'[\\/]')).last;

Color _statusColor(BrainStatus status) => switch (status) {
      BrainStatus.ready => C.mint,
      BrainStatus.loading => C.amber,
      BrainStatus.error => C.red,
      BrainStatus.noModel || BrainStatus.idle => C.text3,
    };

class BrainScreen extends StatelessWidget {
  const BrainScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final brain = context.session.brain!;
    return Scaffold(
      body: HudBackground(
        child: SafeArea(
          child: ListView(
            padding: const EdgeInsets.fromLTRB(S.side, S.sm, S.side, S.huge),
            children: [
              const BackHeader('Brain'),
              const SizedBox(height: S.xl),
              _StatusPanel(brain: brain),
              const SizedBox(height: S.xl),
              const SectionLabel('When to use it'),
              _ModePicker(brain: brain),
              const SizedBox(height: S.xl),
              const SectionLabel('Try it'),
              _TryPanel(brain: brain),
              const SizedBox(height: S.xl),
              const SectionLabel('Speed'),
              _ThreadPicker(brain: brain),
              const SizedBox(height: S.xl),
              const SectionLabel('Recent decisions'),
              _DecisionLog(brain: brain),
            ],
          ),
        ),
      ),
    );
  }
}

/// Model file, load state, and the load / unload / re-scan actions.
class _StatusPanel extends StatelessWidget {
  const _StatusPanel({required this.brain});
  final AerisBrain brain;

  @override
  Widget build(BuildContext context) => ListenableBuilder(
        listenable: Listenable.merge([brain.status, brain.mode]),
        builder: (context, _) {
          final status = brain.status.value;
          return Panel(
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Row(children: [
              StatusDot(color: _statusColor(status), pulse: status == BrainStatus.loading),
              const SizedBox(width: S.sm),
              Expanded(child: Text(_statusLine(brain, status), style: T.body)),
            ]),
            ValueListenableBuilder<String>(
              valueListenable: brain.statusText,
              builder: (context, detail, _) => detail.isEmpty
                  ? const SizedBox.shrink()
                  : Padding(padding: const EdgeInsets.only(top: S.xs), child: Text(detail, style: T.small)),
            ),
            if (status == BrainStatus.noModel) ...[
              const SizedBox(height: S.md),
              Text(
                'Copy a .gguf model to this folder, then tap Re-scan:\n'
                '/sdcard/Android/data/com.aeris.aeris_assistant/files/models/\n\n'
                'Until your own trained model is ready, the stock Qwen3-1.7B-Q4_K_M works.',
                style: T.small,
              ),
            ],
            const SizedBox(height: S.md),
            Wrap(spacing: S.sm, runSpacing: S.sm, children: [
              if (status == BrainStatus.ready)
                HudButton(label: 'Unload', kind: BtnKind.outline, icon: Icons.eject_rounded, onPressed: brain.unload)
              else
                HudButton(
                  label: 'Load now',
                  icon: Icons.play_arrow_rounded,
                  onPressed: brain.hasModel && status != BrainStatus.loading
                      ? () => brain.ensureReady(context.store.settings.lang)
                      : null,
                ),
              HudButton(label: 'Re-scan', kind: BtnKind.outline, icon: Icons.refresh_rounded, onPressed: brain.refreshModel),
            ]),
          ]),
          );
        },
      );
}

/// Off / Shadow / On.
class _ModePicker extends StatelessWidget {
  const _ModePicker({required this.brain});
  final AerisBrain brain;

  static const _explanations = {
    BrainMode.off: 'Only the instant rules answer. Anything they don\'t know becomes a web-search offer.',
    BrainMode.shadow: 'The rules act; the brain decides silently afterwards and both are logged. '
        'A safe way to see how it would do on your real commands.',
    BrainMode.on: 'The rules answer first (instant). The brain handles chat and anything the rules '
        'don\'t understand — still asking before sending messages.',
  };

  @override
  Widget build(BuildContext context) => ValueListenableBuilder<BrainMode>(
        valueListenable: brain.mode,
        builder: (context, mode, _) => Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Segmented<BrainMode>(
            value: mode,
            options: const [(BrainMode.off, 'Off'), (BrainMode.shadow, 'Shadow'), (BrainMode.on, 'On')],
            onChanged: (newMode) {
              brain.setMode(newMode);
              showSaved(context, 'Brain: ${newMode.name}');
            },
          ),
          const SizedBox(height: S.sm),
          Text(_explanations[mode]!, style: T.small),
        ]),
      );
}

/// CPU threads used for inference (fixed at load time).
class _ThreadPicker extends StatefulWidget {
  const _ThreadPicker({required this.brain});
  final AerisBrain brain;

  @override
  State<_ThreadPicker> createState() => _ThreadPickerState();
}

class _ThreadPickerState extends State<_ThreadPicker> {
  @override
  Widget build(BuildContext context) => Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Segmented<int>(
          value: widget.brain.threads,
          options: const [(2, '2 threads'), (4, '4 threads'), (6, '6 threads')],
          onChanged: (threadCount) async {
            await widget.brain.setThreads(threadCount);
            if (!context.mounted) return;
            setState(() {});
            showSaved(context, '$threadCount threads — reloads on next use');
          },
        ),
        const SizedBox(height: S.sm),
        const Text('4 was fastest on this phone (big cores). More threads can be slower when the phone is warm.',
            style: T.small),
      ]);
}

/// Type a sentence, see exactly what the brain decides and how long it took.
/// Doesn't act and doesn't change the conversation.
class _TryPanel extends StatefulWidget {
  const _TryPanel({required this.brain});
  final AerisBrain brain;

  @override
  State<_TryPanel> createState() => _TryPanelState();
}

class _TryPanelState extends State<_TryPanel> {
  final _input = TextEditingController(text: 'kal subah 7 baje ka alarm laga do');
  BrainDecision? _decision;
  bool _thinking = false;

  @override
  void dispose() {
    _input.dispose();
    super.dispose();
  }

  Future<void> _ask() async {
    final sentence = _input.text.trim();
    if (sentence.isEmpty || _thinking) return;
    setState(() => _thinking = true);
    final store = context.store;
    final decision = await widget.brain
        .decide(sentence, lang: store.settings.lang, memories: store.memories, commit: false);
    if (decision != null) await widget.brain.log(decision, mode: 'try');
    if (mounted) {
      setState(() {
        _decision = decision;
        _thinking = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final decision = _decision;
    return Panel(
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        TextField(
          controller: _input,
          style: T.body,
          textInputAction: TextInputAction.send,
          onSubmitted: (_) => _ask(),
          decoration: const InputDecoration(hintText: 'Say something to AERIS…'),
        ),
        const SizedBox(height: S.md),
        HudButton(
          label: _thinking ? 'Thinking…' : 'Ask the brain',
          icon: Icons.psychology_outlined,
          onPressed: widget.brain.hasModel && !_thinking ? _ask : null,
        ),
        if (decision != null) ...[
          const SizedBox(height: S.md),
          _DecisionSummary(
            summary: decision.summary,
            valid: decision.valid,
            milliseconds: decision.totalMs,
            firstTokenMs: decision.gen?.firstTokenMs,
            tokensPerSecond: decision.gen?.tokPerSec,
          ),
        ],
      ]),
    );
  }
}

/// One decision: what the brain chose + timing. Used by the try box and the log.
class _DecisionSummary extends StatelessWidget {
  const _DecisionSummary({
    required this.summary,
    required this.valid,
    required this.milliseconds,
    this.said,
    this.mode,
    this.firstTokenMs,
    this.tokensPerSecond,
  });
  final String summary;
  final bool valid;
  final int milliseconds;
  final String? said;
  final String? mode;
  final int? firstTokenMs;
  final double? tokensPerSecond;

  @override
  Widget build(BuildContext context) {
    final timing = [
      '${(milliseconds / 1000).toStringAsFixed(1)} s',
      if (firstTokenMs != null) 'first token ${(firstTokenMs! / 1000).toStringAsFixed(1)} s',
      if (tokensPerSecond != null && tokensPerSecond! > 0) '${tokensPerSecond!.toStringAsFixed(1)} tok/s',
    ].join(' · ');
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      if (said != null) Text('"$said"', style: T.bodyDim),
      const SizedBox(height: 2),
      Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Tag(valid ? 'ok' : 'invalid', color: valid ? C.mint : C.red),
        if (mode != null) ...[const SizedBox(width: S.xs), Tag(mode!)],
        const SizedBox(width: S.sm),
        Expanded(child: Text(summary, style: T.mono)),
      ]),
      const SizedBox(height: 2),
      Text(timing, style: T.small),
    ]);
  }
}

/// The last decisions from brain_log.jsonl (also the raw material for the
/// next training round).
class _DecisionLog extends StatefulWidget {
  const _DecisionLog({required this.brain});
  final AerisBrain brain;

  @override
  State<_DecisionLog> createState() => _DecisionLogState();
}

class _DecisionLogState extends State<_DecisionLog> {
  late Future<List<Map<String, dynamic>>> _entries = widget.brain.recentLog(20);

  void _reload() => setState(() => _entries = widget.brain.recentLog(20));

  @override
  Widget build(BuildContext context) => FutureBuilder<List<Map<String, dynamic>>>(
        future: _entries,
        builder: (context, snapshot) {
          final entries = snapshot.data ?? const [];
          return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            if (entries.isEmpty)
              const Text('Nothing yet. Decisions appear here as you use AERIS.', style: T.small)
            else
              RowGroup(children: [
                for (final entry in entries)
                  Padding(
                    padding: const EdgeInsets.symmetric(horizontal: S.lg, vertical: S.md),
                    child: _DecisionSummary(
                      said: '${entry['text']}',
                      mode: '${entry['mode']}',
                      summary: '${entry['summary']}',
                      valid: entry['valid'] == true,
                      milliseconds: (entry['ms'] as num?)?.toInt() ?? 0,
                      firstTokenMs: (entry['ttft_ms'] as num?)?.toInt(),
                      tokensPerSecond: (entry['tok_s'] as num?)?.toDouble(),
                    ),
                  ),
              ]),
            const SizedBox(height: S.sm),
            Row(children: [
              HudButton(label: 'Refresh', kind: BtnKind.outline, icon: Icons.refresh_rounded, onPressed: _reload),
              const SizedBox(width: S.sm),
              FutureBuilder<File>(
                future: widget.brain.logFile(),
                builder: (context, file) => Expanded(
                  child: Text(file.data?.path ?? '', style: T.label, overflow: TextOverflow.ellipsis),
                ),
              ),
            ]),
          ]);
        },
      );
}
