import 'package:flutter/material.dart' hide Router;
import 'package:flutter_animate/flutter_animate.dart';

import '../../app/scope.dart';
import '../../brain/executor.dart';
import '../../brain/router.dart';
import '../../core/models.dart';
import '../../core/store.dart';
import '../../ui/kit/controls.dart';
import '../../ui/kit/surfaces.dart';
import '../../ui/tokens.dart';
import '../log/log_screen.dart';

/// "One phrase, many actions."
class ProtocolsScreen extends StatelessWidget {
  const ProtocolsScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final store = context.store;
    return SafeArea(
      bottom: false,
      child: ListenableBuilder(
        listenable: store,
        builder: (context, _) {
          final items = store.protocols;
          return CustomScrollView(slivers: [
            SliverToBoxAdapter(
              child: PageHeader(
                title: 'Protocols',
                subtitle: 'Say one phrase, AERIS runs several actions.',
                trailing: IconBtn(Icons.add_rounded, tooltip: 'New protocol', color: C.cyan, onTap: () => _open(context, null)),
              ),
            ),
            SliverPadding(
              padding: const EdgeInsets.fromLTRB(S.side, 0, S.side, S.xxl),
              sliver: SliverList.builder(
                itemCount: items.length,
                itemBuilder: (context, i) => Padding(
                  padding: const EdgeInsets.only(bottom: S.md),
                  child: _Card(items[i]),
                ).animate().fadeIn(duration: M.base, delay: M.stagger * i).moveY(begin: 6, end: 0, curve: M.ease),
              ),
            ),
          ]);
        },
      ),
    );
  }

  static void _open(BuildContext context, Protocol? p) => Navigator.of(context)
      .push(MaterialPageRoute(builder: (_) => ProtocolEditor(protocol: p)));
}

class _Card extends StatelessWidget {
  const _Card(this.p);
  final Protocol p;

  @override
  Widget build(BuildContext context) {
    final store = context.store;
    return Panel(
      onTap: () => ProtocolsScreen._open(context, p),
      borderColor: p.enabled ? C.hairline : C.hairlineSoft,
      child: Opacity(
        opacity: p.enabled ? 1 : 0.55,
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Row(children: [
            Expanded(child: Text(p.name, style: T.heading)),
            Switch(
              value: p.enabled,
              onChanged: (v) {
                store.upsertProtocol(p.copyWith(enabled: v));
                showSaved(context, v ? '${p.name} on' : '${p.name} off');
              },
            ),
          ]),
          const SizedBox(height: 2),
          Text('Say "${p.phrase}"', style: T.bodyDim),
          const SizedBox(height: S.md),
          Wrap(spacing: S.sm, runSpacing: S.sm, children: [
            for (final a in p.actions) _ActionPill(a),
          ]),
          const SizedBox(height: S.md),
          Row(children: [
            Text('${p.actions.length} ${p.actions.length == 1 ? 'ACTION' : 'ACTIONS'}', style: T.label),
            const Spacer(),
            if (p.enabled)
              TextButton.icon(
                onPressed: () => context.session.submitText(p.phrase),
                icon: const Icon(Icons.play_arrow_rounded, size: 18, color: C.cyan),
                label: Text('Run', style: T.body.copyWith(color: C.cyan, fontSize: 14)),
              ),
          ]),
        ]),
      ),
    );
  }
}

class _ActionPill extends StatelessWidget {
  const _ActionPill(this.cmd);
  final String cmd;

  @override
  Widget build(BuildContext context) {
    final plan = const Router().route(cmd);
    final ok = !plan.needsApproval && plan.tool != 'clarify';
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
      decoration: ShapeDecoration(
        color: C.bg,
        shape: ChamferBorder(cut: 4, side: BorderSide(color: ok ? C.hairline : C.amber.withValues(alpha: 0.5))),
      ),
      child: Row(mainAxisSize: MainAxisSize.min, children: [
        Icon(ok ? LogScreen.iconFor(plan.tool) : Icons.help_outline_rounded, size: 14, color: ok ? C.cyanDim : C.amber),
        const SizedBox(width: 6),
        Text(cmd, style: T.small.copyWith(color: C.text1, fontSize: 12.5)),
      ]),
    );
  }
}

/// Editor — explicit Save (enabled when changed) + discard guard.
class ProtocolEditor extends StatefulWidget {
  const ProtocolEditor({super.key, this.protocol});
  final Protocol? protocol;

  @override
  State<ProtocolEditor> createState() => _ProtocolEditorState();
}

class _ProtocolEditorState extends State<ProtocolEditor> {
  late final Protocol _orig = widget.protocol ??
      Protocol(id: Store.newId(), name: '', phrase: '', actions: const []);
  late final _name = TextEditingController(text: _orig.name);
  late final _phrase = TextEditingController(text: _orig.phrase);
  late final _actions = TextEditingController(text: _orig.actions.join('\n'));
  late final _say = TextEditingController(text: _orig.sayAfter);

  @override
  void initState() {
    super.initState();
    for (final c in [_name, _phrase, _actions, _say]) {
      c.addListener(() => setState(() {}));
    }
  }

  @override
  void dispose() {
    for (final c in [_name, _phrase, _actions, _say]) {
      c.dispose();
    }
    super.dispose();
  }

  List<String> get _lines => _actions.text.split('\n').map((l) => l.trim()).where((l) => l.isNotEmpty).toList();

  Protocol get _draft => _orig.copyWith(
        name: _name.text.trim(),
        phrase: _phrase.text.trim(),
        actions: _lines,
        sayAfter: _say.text.trim(),
      );

  bool get _dirty {
    final d = _draft;
    return d.name != _orig.name ||
        d.phrase != _orig.phrase ||
        d.sayAfter != _orig.sayAfter ||
        d.actions.join('\n') != _orig.actions.join('\n');
  }

  bool get _valid => _name.text.trim().isNotEmpty && _phrase.text.trim().isNotEmpty && _lines.isNotEmpty;

  void _save() {
    context.store.upsertProtocol(_draft);
    showSaved(context);
    Navigator.of(context).pop();
  }

  @override
  Widget build(BuildContext context) {
    final isNew = widget.protocol == null;
    return PopScope(
      canPop: !_dirty,
      onPopInvokedWithResult: (didPop, _) async {
        if (didPop) return;
        if (await confirm(context, title: 'Discard changes?', body: 'This protocol has unsaved changes.', action: 'Discard') &&
            context.mounted) {
          Navigator.of(context).pop();
        }
      },
      child: Scaffold(
        body: HudBackground(
          child: SafeArea(
            child: Column(children: [
              Padding(
                padding: const EdgeInsets.fromLTRB(S.xs, S.sm, S.side, 0),
                child: Row(children: [
                  IconBtn(Icons.arrow_back_rounded, onTap: () => Navigator.of(context).maybePop()),
                  const SizedBox(width: S.xs),
                  Text(isNew ? 'New protocol' : 'Edit protocol', style: T.heading),
                  const Spacer(),
                  HudButton(label: 'Save', onPressed: _dirty && _valid ? _save : null),
                ]),
              ),
              Expanded(
                child: ListView(padding: const EdgeInsets.fromLTRB(S.side, S.xl, S.side, S.xxl), children: [
                  _field('NAME', _name, 'e.g. Work mode'),
                  _field('WHEN I SAY', _phrase, 'e.g. work mode on'),
                  _field('DO THESE — ONE PER LINE', _actions, 'torch off\n25 minute ka timer\nbattery kitni hai', lines: 5),
                  if (_lines.isNotEmpty) ...[
                    Wrap(spacing: S.sm, runSpacing: S.sm, children: [for (final l in _lines) _ActionPill(l)]),
                    const SizedBox(height: S.sm),
                    Text('Amber actions need a question or approval, so protocols skip them.', style: T.small),
                    const SizedBox(height: S.xl),
                  ],
                  _field('THEN SAY (OPTIONAL)', _say, 'e.g. Work mode on. All the best!'),
                  const SizedBox(height: S.md),
                  if (!isNew) ...[
                    HudButton(
                      label: 'Test run',
                      icon: Icons.play_arrow_rounded,
                      kind: BtnKind.outline,
                      onPressed: _dirty ? null : () => context.session.submitText(_orig.phrase),
                    ),
                    const SizedBox(height: S.xl),
                    Align(
                      alignment: Alignment.centerLeft,
                      child: TextButton.icon(
                        onPressed: () async {
                          if (!await confirm(context, title: 'Delete "${_orig.name}"?', body: 'You can undo right after.')) return;
                          if (!context.mounted) return;
                          final store = context.store;
                          final idx = store.protocols.indexWhere((p) => p.id == _orig.id);
                          store.removeProtocol(_orig.id);
                          final messenger = ScaffoldMessenger.of(context);
                          Navigator.of(context).pop();
                          messenger.showSnackBar(SnackBar(
                            content: Text('${_orig.name} deleted'),
                            action: SnackBarAction(label: 'Undo', onPressed: () => store.restoreProtocol(_orig, idx)),
                          ));
                        },
                        icon: const Icon(Icons.delete_outline_rounded, color: C.red, size: 18),
                        label: Text('Delete protocol', style: T.body.copyWith(color: C.red, fontSize: 14)),
                      ),
                    ),
                  ],
                ]),
              ),
              if (_dirty)
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: S.side, vertical: S.md),
                  decoration: const BoxDecoration(color: C.surfaceHi, border: Border(top: BorderSide(color: C.hairline))),
                  child: Row(children: [
                    const Icon(Icons.edit_note_rounded, color: C.amber, size: 20),
                    const SizedBox(width: S.sm),
                    Text('Unsaved changes', style: T.small.copyWith(color: C.text1)),
                    const Spacer(),
                    TextButton(
                      onPressed: () {
                        _name.text = _orig.name;
                        _phrase.text = _orig.phrase;
                        _actions.text = _orig.actions.join('\n');
                        _say.text = _orig.sayAfter;
                      },
                      child: Text('Discard', style: T.small.copyWith(color: C.text2)),
                    ),
                  ]),
                ),
            ]),
          ),
        ),
      ),
    );
  }

  Widget _field(String label, TextEditingController c, String hint, {int lines = 1}) => Padding(
        padding: const EdgeInsets.only(bottom: S.xl),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text(label, style: T.label),
          const SizedBox(height: S.sm),
          Panel(
            padding: const EdgeInsets.symmetric(horizontal: S.lg, vertical: S.md),
            child: TextField(
              controller: c,
              minLines: lines,
              maxLines: lines == 1 ? 1 : 10,
              style: T.body.copyWith(fontSize: 14.5),
              decoration: InputDecoration(hintText: hint),
            ),
          ),
        ]),
      );
}

/// Label helper re-export so other screens don't import executor directly.
String protocolActionLabel(String cmd) => toolLabel(const Router().route(cmd).tool);
