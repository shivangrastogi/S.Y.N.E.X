import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';

import '../../app/scope.dart';
import '../../core/models.dart';
import '../../core/store.dart';
import '../../ui/kit/controls.dart';
import '../../ui/kit/surfaces.dart';
import '../../ui/tokens.dart';
import '../log/log_screen.dart';

class MemoryScreen extends StatefulWidget {
  const MemoryScreen({super.key});

  @override
  State<MemoryScreen> createState() => _MemoryScreenState();
}

class _MemoryScreenState extends State<MemoryScreen> {
  String _q = '';

  @override
  Widget build(BuildContext context) {
    final store = context.store;
    return SafeArea(
      bottom: false,
      child: ListenableBuilder(
        listenable: store,
        builder: (context, _) {
          final all = store.memories;
          final q = _q.toLowerCase();
          final items = q.isEmpty ? all : all.where((m) => m.text.toLowerCase().contains(q)).toList();
          return CustomScrollView(slivers: [
            SliverToBoxAdapter(
              child: PageHeader(
                title: 'Memory',
                subtitle: all.isEmpty
                    ? 'Things you ask AERIS to remember. Only on this phone.'
                    : '${all.length} ${all.length == 1 ? 'thing' : 'things'} remembered · only on this phone',
                trailing: IconBtn(Icons.add_rounded, tooltip: 'Add', color: C.cyan, onTap: () => _edit(context, store, null)),
              ),
            ),
            if (all.length > 4)
              SliverToBoxAdapter(
                child: Padding(
                  padding: const EdgeInsets.fromLTRB(S.side, 0, S.side, S.lg),
                  child: Panel(
                    padding: const EdgeInsets.symmetric(horizontal: S.lg),
                    child: Row(children: [
                      const Icon(Icons.search_rounded, size: 18, color: C.text3),
                      const SizedBox(width: S.sm),
                      Expanded(
                        child: TextField(
                          onChanged: (v) => setState(() => _q = v),
                          style: T.body.copyWith(fontSize: 14),
                          decoration: const InputDecoration(
                              hintText: 'Search memory', contentPadding: EdgeInsets.symmetric(vertical: 14)),
                        ),
                      ),
                    ]),
                  ),
                ),
              ),
            if (all.isEmpty)
              SliverFillRemaining(
                hasScrollBody: false,
                child: Padding(
                  padding: const EdgeInsets.all(S.huge),
                  child: Column(mainAxisAlignment: MainAxisAlignment.center, children: [
                    Icon(Icons.bookmark_border_rounded, size: 40, color: C.text3.withValues(alpha: 0.6)),
                    const SizedBox(height: S.lg),
                    const Text('I don\'t know much about you yet.', style: T.heading, textAlign: TextAlign.center),
                    const SizedBox(height: S.sm),
                    const Text('Say "yaad rakho ki meri car B2 mein parked hai" — then later ask "car kahan park ki thi?"',
                        style: T.bodyDim, textAlign: TextAlign.center),
                    const SizedBox(height: S.xl),
                    HudButton(label: 'Add a memory', kind: BtnKind.outline, onPressed: () => _edit(context, store, null)),
                  ]),
                ),
              )
            else
              SliverPadding(
                padding: const EdgeInsets.fromLTRB(S.side, 0, S.side, S.xxl),
                sliver: SliverList.builder(
                  itemCount: items.length,
                  itemBuilder: (context, i) {
                    final m = items[i];
                    return Padding(
                      padding: const EdgeInsets.only(bottom: S.sm),
                      child: Dismissible(
                        key: ValueKey(m.id),
                        direction: DismissDirection.endToStart,
                        background: Container(
                          alignment: Alignment.centerRight,
                          padding: const EdgeInsets.only(right: S.xl),
                          child: const Icon(Icons.delete_outline_rounded, color: C.red),
                        ),
                        onDismissed: (_) {
                          final idx = store.memories.indexOf(m);
                          store.removeMemory(m.id);
                          showUndo(context, 'Memory deleted', () => store.restoreMemory(m, idx));
                        },
                        child: Panel(
                          onTap: () => _edit(context, store, m),
                          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                            Text(m.text, style: T.body),
                            const SizedBox(height: S.sm),
                            Text('SAVED ${_date(m.createdAt)}', style: T.label.copyWith(fontSize: 9.5)),
                          ]),
                        ),
                      ),
                    ).animate().fadeIn(duration: M.base, delay: M.stagger * (i < 10 ? i : 10));
                  },
                ),
              ),
          ]);
        },
      ),
    );
  }

  static String _date(DateTime d) {
    const m = ['JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN', 'JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC'];
    return '${d.day} ${m[d.month - 1]}';
  }

  static Future<void> _edit(BuildContext context, Store store, Memory? m) async {
    final result = await showModalBottomSheet<String>(
      context: context,
      isScrollControlled: true,
      showDragHandle: true,
      builder: (_) => _MemoryEditor(initial: m?.text ?? '', isNew: m == null),
    );
    if (result == null || !context.mounted) return;
    if (result == '\u0000delete' && m != null) {
      final idx = store.memories.indexOf(m);
      store.removeMemory(m.id);
      showUndo(context, 'Memory deleted', () => store.restoreMemory(m, idx));
      return;
    }
    if (m == null) {
      store.addMemory(result);
    } else {
      store.updateMemory(m.copyWith(text: result));
    }
    showSaved(context);
  }
}

/// Text form → explicit Save, enabled only when changed; leaving with
/// changes asks first (standard save protocol).
class _MemoryEditor extends StatefulWidget {
  const _MemoryEditor({required this.initial, required this.isNew});
  final String initial;
  final bool isNew;

  @override
  State<_MemoryEditor> createState() => _MemoryEditorState();
}

class _MemoryEditorState extends State<_MemoryEditor> {
  late final _c = TextEditingController(text: widget.initial)..addListener(() => setState(() {}));

  bool get _dirty => _c.text.trim() != widget.initial.trim() && _c.text.trim().isNotEmpty;

  @override
  void dispose() {
    _c.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return PopScope(
      canPop: !_dirty,
      onPopInvokedWithResult: (didPop, _) async {
        if (didPop) return;
        if (await confirm(context, title: 'Discard changes?', body: 'Your edit hasn\'t been saved.', action: 'Discard') &&
            context.mounted) {
          Navigator.of(context).pop();
        }
      },
      child: Padding(
        padding: EdgeInsets.fromLTRB(S.side, 0, S.side, MediaQuery.viewInsetsOf(context).bottom + S.xl),
        child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text(widget.isNew ? 'New memory' : 'Edit memory', style: T.heading),
          const SizedBox(height: S.lg),
          Panel(
            fill: C.bg,
            padding: const EdgeInsets.symmetric(horizontal: S.lg, vertical: S.md),
            child: TextField(
              controller: _c,
              autofocus: widget.isNew,
              minLines: 2,
              maxLines: 6,
              style: T.body,
              textCapitalization: TextCapitalization.sentences,
              decoration: const InputDecoration(hintText: 'e.g. My car is parked at B2, pillar 14'),
            ),
          ),
          const SizedBox(height: S.lg),
          Row(children: [
            if (!widget.isNew)
              TextButton.icon(
                onPressed: () async {
                  if (await confirm(context, title: 'Delete this memory?', body: 'AERIS will forget it.') && context.mounted) {
                    Navigator.of(context).pop('\u0000delete');
                  }
                },
                icon: const Icon(Icons.delete_outline_rounded, color: C.red, size: 18),
                label: Text('Delete', style: T.body.copyWith(color: C.red, fontSize: 14)),
              ),
            const Spacer(),
            HudButton(label: 'Save', onPressed: _dirty ? () => Navigator.of(context).pop(_c.text.trim()) : null),
          ]),
        ]),
      ),
    );
  }
}
