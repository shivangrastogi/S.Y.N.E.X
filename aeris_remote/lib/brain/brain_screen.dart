// Brain screen: pick the model, switch off / shadow / on, and test the
// brain by typing — see exactly what it decided, how fast, and run it.
// Also shows the shadow log so you can judge it on your own commands.
import 'dart:convert';
import 'dart:io';

import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:path_provider/path_provider.dart';

import '../ui/theme.dart';
import '../ui/kit.dart';
import 'brain.dart';
import 'executor.dart';

class BrainScreen extends StatefulWidget {
  const BrainScreen({super.key});
  @override
  State<BrainScreen> createState() => _BrainScreenState();
}

class _BrainScreenState extends State<BrainScreen> {
  final _brain = AerisBrain.instance;
  final _input = TextEditingController();
  List<File> _models = [];
  String _pushPath = '';
  BrainDecision? _last;
  String? _ran;
  bool _deciding = false;
  double? _copyProgress;
  List<Map<String, dynamic>> _log = [];

  @override
  void initState() {
    super.initState();
    _refresh();
  }

  Future<void> _refresh() async {
    final models = await AerisBrain.findModels();
    final dirs = await AerisBrain.modelDirs();
    final log = await _readLog();
    if (!mounted) return;
    setState(() {
      _models = models;
      _pushPath = dirs.first.path;
      _log = log;
    });
  }

  Future<List<Map<String, dynamic>>> _readLog() async {
    final f = await _brain.logFile();
    if (!await f.exists()) return [];
    final lines = (await f.readAsLines()).where((l) => l.trim().isNotEmpty).toList();
    return [
      for (final l in lines.reversed.take(200))
        if (jsonDecode(l) case final Map<String, dynamic> m) m
    ];
  }

  Future<void> _pick() async {
    final res = await FilePicker.platform.pickFiles(type: FileType.any, withData: false);
    final src = res?.files.single.path;
    if (src == null) return;
    if (!src.toLowerCase().endsWith('.gguf')) {
      _toast('Pick a .gguf model file');
      return;
    }
    // Copy into private storage: a picked path can live in a cache that
    // Android clears, and the model must outlive it.
    final dir = Directory('${(await getApplicationSupportDirectory()).path}/models');
    await dir.create(recursive: true);
    final dst = File('${dir.path}/${src.split('/').last}');
    final total = await File(src).length();
    var done = 0;
    setState(() => _copyProgress = 0);
    final sink = dst.openWrite();
    await for (final chunk in File(src).openRead()) {
      sink.add(chunk);
      done += chunk.length;
      if (mounted) setState(() => _copyProgress = done / total);
    }
    await sink.close();
    try {
      await File(src).delete(); // file_picker's cache copy
    } catch (_) {}
    setState(() => _copyProgress = null);
    await _brain.setModelPath(dst.path);
    _refresh();
  }

  Future<void> _decide() async {
    final text = _input.text.trim();
    if (text.isEmpty || _deciding) return;
    FocusScope.of(context).unfocus();
    setState(() {
      _deciding = true;
      _ran = null;
    });
    final d = await _brain.decide(text, commit: false);
    if (d != null) await _brain.log(d, mode: 'test');
    if (!mounted) return;
    setState(() {
      _deciding = false;
      _last = d;
    });
    _refresh();
  }

  Future<void> _run() async {
    final d = _last;
    if (d == null || !d.valid) return;
    String said;
    if (d.type == 'tool_call') {
      final r = await BrainExecutor().runAll(d.calls);
      said = '${r.outcome.name}: ${r.spoken}';
    } else {
      said = d.obj!['text'] as String? ?? d.summary;
    }
    setState(() => _ran = said);
  }

  void _toast(String s) => showSaved(context, s);

  @override
  Widget build(BuildContext context) {
    return PageScaffold(
      title: 'On-device brain',
      onRefresh: _refresh,
      children: [
        const SizedBox(height: 4),
        _statusCard(),
        ValueListenableBuilder(
          valueListenable: _brain.mode,
          builder: (_, m, __) => Section(
            title: 'Mode',
            footer: switch (m) {
              BrainMode.off => 'Rules and the cloud handle everything, as before.',
              BrainMode.shadow =>
                'The old path acts. The brain decides silently and both are logged below — use this first to see its accuracy on your own commands.',
              BrainMode.on => 'The brain decides first. Invalid or unsure answers fall back to the old path.',
            },
            children: [
              ChoiceRow<BrainMode>(
                options: const [(BrainMode.off, 'Off'), (BrainMode.shadow, 'Shadow'), (BrainMode.on, 'On')],
                value: m,
                onChanged: (v) async {
                  await _brain.setMode(v);
                  if (mounted) _toast('Brain mode: ${v.name[0].toUpperCase()}${v.name.substring(1)}');
                },
              ),
            ],
          ),
        ),
        Section(title: 'Try it', children: [
          Padding(
            padding: const EdgeInsets.all(12),
            child: TextField(
              controller: _input,
              onSubmitted: (_) => _decide(),
              textInputAction: TextInputAction.send,
              decoration: InputDecoration(
                hintText: 'e.g. Ravi ko bolo main late hoon',
                fillColor: A.deck,
                suffixIcon: _deciding
                    ? const Padding(
                        padding: EdgeInsets.all(14),
                        child: SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2)))
                    : IconButton(tooltip: 'Decide', icon: const Icon(Icons.arrow_upward), onPressed: _decide),
              ),
            ),
          ),
          if (_last != null) _decisionCard(_last!),
        ]),
        _modelSection(),
        _logSection(),
      ],
    );
  }

  Widget _statusCard() => ValueListenableBuilder(
        valueListenable: _brain.status,
        builder: (_, st, __) {
          final (tone, label) = switch (st) {
            BrainStatus.noModel => (BadgeTone.bad, 'No model'),
            BrainStatus.idle => (BadgeTone.neutral, 'Sleeping'),
            BrainStatus.loading => (BadgeTone.accent, 'Loading'),
            BrainStatus.ready => (BadgeTone.ok, 'Ready'),
            BrainStatus.error => (BadgeTone.bad, 'Error'),
          };
          return Container(
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
                color: A.panel, borderRadius: BorderRadius.circular(A.radius), border: Border.all(color: A.line)),
            child: Row(children: [
              AerisOrb(size: 52, online: st == BrainStatus.ready, active: st == BrainStatus.loading),
              const SizedBox(width: 14),
              Expanded(
                child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  Row(children: [
                    StatusBadge(label, tone: tone),
                  ]),
                  const SizedBox(height: 6),
                  ValueListenableBuilder(
                    valueListenable: _brain.statusText,
                    builder: (_, t, __) => Text(
                        t.isEmpty
                            ? (st == BrainStatus.idle ? 'Loads by itself on first use' : '')
                            : t,
                        style: const TextStyle(color: A.muted, fontSize: 12)),
                  ),
                  if (_brain.modelPath != null)
                    Padding(
                      padding: const EdgeInsets.only(top: 4),
                      child: Text(_brain.modelPath!.split('/').last,
                          overflow: TextOverflow.ellipsis,
                          style: const TextStyle(color: A.faint, fontSize: 11, fontFamily: A.mono)),
                    ),
                ]),
              ),
              if (st == BrainStatus.ready)
                OutlinedButton(onPressed: _brain.unload, child: const Text('Unload'))
              else if (st == BrainStatus.idle || st == BrainStatus.error)
                OutlinedButton(onPressed: _brain.ensureReady, child: const Text('Load')),
            ]),
          );
        },
      );

  Widget _decisionCard(BrainDecision d) {
    final g = d.gen;
    return Container(
      margin: const EdgeInsets.fromLTRB(12, 0, 12, 12),
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: A.deck,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: d.valid ? A.line : A.hot.withValues(alpha: .5)),
      ),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          StatusBadge(d.valid ? (d.type ?? '') : 'invalid', tone: d.valid ? BadgeTone.accent : BadgeTone.bad),
          const Spacer(),
          Text(
              [
                '${(d.totalMs / 1000).toStringAsFixed(1)} s',
                if (g != null && g.tokPerSec > 0) '${g.tokPerSec.toStringAsFixed(1)} tok/s',
              ].join(' · '),
              style: const TextStyle(color: A.faint, fontSize: 11, fontFamily: A.mono)),
        ]),
        const SizedBox(height: 10),
        Text(d.summary, style: const TextStyle(color: A.text, fontSize: 14.5, fontWeight: FontWeight.w500)),
        const SizedBox(height: 8),
        SelectableText(d.raw, style: const TextStyle(color: A.muted, fontSize: 11.5, fontFamily: A.mono)),
        if (d.errors.isNotEmpty)
          Padding(
            padding: const EdgeInsets.only(top: 6),
            child: Text(d.errors.join('\n'), style: const TextStyle(color: A.hot, fontSize: 12)),
          ),
        if (d.valid) ...[
          const SizedBox(height: 10),
          Row(children: [
            if (_ran != null)
              Expanded(child: Text(_ran!, style: const TextStyle(color: A.accent, fontSize: 12.5)))
            else
              const Spacer(),
            FilledButton.icon(
              style: FilledButton.styleFrom(minimumSize: const Size(90, 38)),
              onPressed: _run,
              icon: const Icon(Icons.play_arrow, size: 18),
              label: const Text('Run'),
            ),
          ]),
        ],
      ]),
    );
  }

  Widget _modelSection() => Section(
        title: 'Model',
        footer: 'A .gguf file. From a PC: adb push model.gguf $_pushPath/',
        children: [
          for (final f in _models)
            SettingsTile(
              icon: f.path == _brain.modelPath ? Icons.radio_button_checked : Icons.radio_button_off,
              title: f.path.split('/').last,
              subtitle: '${(f.lengthSync() / 1e9).toStringAsFixed(2)} GB',
              chevron: false,
              onTap: () async {
                await _brain.setModelPath(f.path);
                setState(() {});
                _toast('Model selected');
              },
            ),
          SettingsTile(
            icon: Icons.file_open_outlined,
            title: 'Add a model file',
            subtitle: _copyProgress == null ? 'Copied into the app (needs ~2 GB free)' : null,
            trailing: _copyProgress == null
                ? null
                : SizedBox(width: 80, child: LinearProgressIndicator(value: _copyProgress)),
            onTap: _copyProgress == null ? _pick : null,
          ),
          SettingsTile(
            icon: Icons.speed,
            title: 'CPU threads',
            subtitle: 'More is faster until the phone gets hot. 4 suits most phones.',
            trailing: DropdownButton<int>(
              value: _brain.threads,
              underline: const SizedBox.shrink(),
              dropdownColor: A.panelHi,
              items: [for (final n in [2, 3, 4, 6, 8]) DropdownMenuItem(value: n, child: Text('$n'))],
              onChanged: (n) async {
                await _brain.setThreads(n!);
                setState(() {});
                _toast('Threads: $n (reloads on next use)');
              },
            ),
          ),
        ],
      );

  Widget _logSection() {
    final shadow = _log.where((m) => m['mode'] == 'shadow').toList();
    final valid = shadow.where((m) => m['valid'] == true).length;
    final avgMs = shadow.isEmpty
        ? 0
        : shadow.map((m) => (m['ms'] as num?) ?? 0).reduce((a, b) => a + b) / shadow.length;
    return Section(
      title: 'Recent decisions',
      footer: shadow.isEmpty
          ? null
          : 'Shadow: ${shadow.length} turns · ${(100 * valid / shadow.length).round()}% valid · '
              'avg ${(avgMs / 1000).toStringAsFixed(1)} s',
      children: [
        if (_log.isEmpty)
          const SettingsTile(title: 'Nothing yet', subtitle: 'Use Shadow mode, or try a sentence above.'),
        for (final m in _log.take(30))
          SettingsTile(
            title: '${m['text']}',
            subtitle: '${m['summary']}${m['legacy'] != null ? '  ·  old: ${m['legacy']}' : ''}',
            trailing: Icon(m['valid'] == true ? Icons.check : Icons.close,
                size: 16, color: m['valid'] == true ? A.ok : A.hot),
          ),
        if (_log.isNotEmpty)
          SettingsTile(
            icon: Icons.copy_all,
            title: 'Copy log',
            chevron: false,
            onTap: () {
              Clipboard.setData(ClipboardData(text: _log.reversed.map(jsonEncode).join('\n')));
              _toast('Copied ${_log.length} log lines');
            },
          ),
      ],
    );
  }
}
