import 'package:flutter/material.dart';
import 'package:permission_handler/permission_handler.dart';

import '../../app/scope.dart';
import '../../core/models.dart';
import '../../ui/kit/controls.dart';
import '../../ui/kit/surfaces.dart';
import '../../ui/tokens.dart';
import 'brain_screen.dart';
import 'call_settings.dart';
import 'permission_row.dart';
import 'self_test.dart';

/// Switches/choices apply instantly + "Saved". Text forms have explicit Save.
class SettingsScreen extends StatefulWidget {
  const SettingsScreen({super.key});

  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  @override
  Widget build(BuildContext context) {
    final store = context.store;
    final session = context.session;
    return Scaffold(
      body: HudBackground(
        child: SafeArea(
          child: ListenableBuilder(
            listenable: store,
            builder: (context, _) {
              final s = store.settings;
              void set(Settings n, [String msg = 'Saved']) {
                store.updateSettings(n);
                showSaved(context, msg);
              }

              final st = store.stats();
              return ListView(padding: const EdgeInsets.fromLTRB(S.side, S.sm, S.side, S.huge), children: [
                const BackHeader('Settings'),
                const SizedBox(height: S.xl),

                const SectionLabel('You'),
                RowGroup(children: [
                  SettingRow(
                    icon: Icons.person_outline_rounded,
                    title: 'Name',
                    subtitle: s.name.isEmpty ? 'Not set' : s.name,
                    trailing: const Icon(Icons.chevron_right_rounded, color: C.text3),
                    onTap: () => _editName(context, s.name),
                  ),
                ]),
                const SizedBox(height: S.xl),

                const SectionLabel('Voice'),
                Segmented<Lang>(
                  value: s.lang,
                  options: const [(Lang.hinglish, 'Hinglish'), (Lang.englishIn, 'English · IN'), (Lang.englishUs, 'English · US')],
                  onChanged: (v) => set(s.copyWith(lang: v), 'Language updated'),
                ),
                const SizedBox(height: S.md),
                RowGroup(children: [
                  const SettingRow(
                    icon: Icons.record_voice_over_outlined,
                    title: 'Voice',
                    subtitle: 'JARVIS — deep male, made on this phone',
                  ),
                  SettingRow(
                    icon: Icons.volume_up_outlined,
                    title: 'Speak replies',
                    subtitle: 'Read answers out loud',
                    trailing: Switch(value: s.speak, onChanged: (v) => set(s.copyWith(speak: v))),
                  ),
                  SettingRow(
                    icon: Icons.all_inclusive_rounded,
                    title: 'Keep listening',
                    subtitle: 'Stay in the conversation until you say "bas" or "bye"',
                    trailing: Switch(value: s.keepListening, onChanged: (v) => set(s.copyWith(keepListening: v))),
                  ),
                  Padding(
                    padding: const EdgeInsets.fromLTRB(S.lg, S.md, S.lg, S.xs),
                    child: Row(children: [
                      const Icon(Icons.speed_rounded, size: 20, color: C.cyanDim),
                      const SizedBox(width: S.md + 2),
                      Text('Speaking speed', style: T.body),
                      const Spacer(),
                      Text('${(s.rate / 0.5).toStringAsFixed(1)}×', style: T.mono),
                      IconBtn(Icons.play_arrow_rounded, tooltip: 'Hear this speed', color: C.cyan, onTap: session.previewVoice),
                    ]),
                  ),
                  // 0.8× … 1.6× in 0.1 steps; 1.0× = the pace Shivang picked
                  Slider(
                    value: s.rate.clamp(0.4, 0.8),
                    min: 0.4,
                    max: 0.8,
                    divisions: 8,
                    onChanged: (v) => store.updateSettings(s.copyWith(rate: v)),
                    onChangeEnd: (_) => showSaved(context, 'Speed ${(store.settings.rate / 0.5).toStringAsFixed(1)}×'),
                  ),
                ]),
                const SizedBox(height: S.xl),

                const SectionLabel('Listening'),
                Segmented<SttEngine>(
                  value: s.stt,
                  options: const [(SttEngine.aeris, 'AERIS · on this phone'), (SttEngine.google, 'Google')],
                  onChanged: (v) => set(s.copyWith(stt: v), v == SttEngine.aeris ? 'Listening on this phone' : 'Listening with Google'),
                ),
                const SizedBox(height: S.sm),
                Text(
                  s.stt == SttEngine.aeris
                      ? 'AERIS records the mic itself and understands you with its own Hinglish model. Nothing leaves the phone, no beep.'
                      : 'Android\'s Google recognizer: slightly better at Hinglish, plays Google\'s beep, sends audio to Google.',
                  style: T.small,
                ),
                const SizedBox(height: S.xl),

                const SectionLabel('Brain'),
                const RowGroup(children: [BrainSettingsRow()]),
                const SizedBox(height: S.xl),

                const SectionLabel('Calls'),
                const CallSettingsSection(),
                const SizedBox(height: S.xl),

                const SectionLabel('Wake word'),
                const Panel(
                  child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
                    Icon(Icons.hearing_rounded, color: C.cyanDim, size: 20),
                    SizedBox(width: S.md + 2),
                    Expanded(
                      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                        Text('"Hey AERIS"', style: T.body),
                        SizedBox(height: 2),
                        Text('In development — the on-device listener (openWakeWord) lands next. Until then, tap the core or the mic.',
                            style: T.small),
                      ]),
                    ),
                  ]),
                ),
                const SizedBox(height: S.xl),

                const SectionLabel('Permissions'),
                const RowGroup(children: [
                  PermissionRow(
                      icon: Icons.mic_none_rounded, title: 'Microphone', why: 'Needed to hear you', permission: Permission.microphone),
                  PermissionRow(
                      icon: Icons.people_outline_rounded,
                      title: 'Contacts',
                      why: 'Call and message by name',
                      permission: Permission.contacts),
                ]),
                const SizedBox(height: S.xl),

                const SectionLabel('Your data'),
                RowGroup(children: [
                  SettingRow(
                    icon: Icons.receipt_long_outlined,
                    title: 'Clear log',
                    subtitle: '${store.activity.length} entries',
                    titleColor: C.red,
                    onTap: store.activity.isEmpty
                        ? null
                        : () async {
                            if (await confirm(context, title: 'Clear the log?', body: 'All entries are removed from this phone.', action: 'Clear')) {
                              store.clearActivity();
                              if (context.mounted) showSaved(context, 'Log cleared');
                            }
                          },
                  ),
                  SettingRow(
                    icon: Icons.bookmark_remove_outlined,
                    title: 'Erase memory',
                    subtitle: '${store.memories.length} remembered',
                    titleColor: C.red,
                    onTap: store.memories.isEmpty
                        ? null
                        : () async {
                            if (await confirm(context,
                                title: 'Erase everything AERIS remembers?', body: 'This can\'t be undone.', action: 'Erase')) {
                              store.clearMemories();
                              if (context.mounted) showSaved(context, 'Memory erased');
                            }
                          },
                  ),
                ]),
                const SizedBox(height: S.xl),

                const SectionLabel('Diagnostics'),
                Panel(
                  child: Column(children: [
                    _stat(
                        'Speech recognition',
                        !session.ears.available
                            ? 'Not started yet'
                            : s.stt == SttEngine.aeris
                                ? 'AERIS · Hinglish Whisper (on-device)'
                                : 'Google · ${s.lang == Lang.englishUs ? 'en-US' : 'en-IN'}'),
                    _stat('Voice output', session.mouth.engineName),
                    _stat('Commands today', '${st.today}'),
                    _stat('Average response', st.avgMs == 0 ? '—' : '${st.avgMs} ms'),
                    _stat('Where it runs', s.stt == SttEngine.aeris ? 'This phone only' : 'This phone + Google speech'),
                  ]),
                ),
                const SizedBox(height: S.md),
                HudButton(
                  label: 'Run self-test',
                  icon: Icons.science_outlined,
                  kind: BtnKind.outline,
                  onPressed: () => showModalBottomSheet<void>(
                    context: context,
                    isScrollControlled: true,
                    showDragHandle: true,
                    builder: (_) => const SelfTestSheet(),
                  ),
                ),
                const SizedBox(height: S.xl),
                Center(child: Text('AERIS 0.1.0 · no account · no analytics', style: T.label)),
              ]);
            },
          ),
        ),
      ),
    );
  }

  Widget _stat(String k, String v) => Padding(
        padding: const EdgeInsets.symmetric(vertical: 6),
        child: Row(children: [
          Text(k, style: T.bodyDim),
          const Spacer(),
          Flexible(child: Text(v, style: T.mono.copyWith(color: C.text1), textAlign: TextAlign.right, overflow: TextOverflow.ellipsis)),
        ]),
      );

  Future<void> _editName(BuildContext context, String current) async {
    final store = context.store;
    final c = TextEditingController(text: current);
    final r = await showModalBottomSheet<String>(
      context: context,
      isScrollControlled: true,
      showDragHandle: true,
      builder: (ctx) => StatefulBuilder(builder: (ctx, setS) {
        final dirty = c.text.trim() != current.trim();
        return Padding(
          padding: EdgeInsets.fromLTRB(S.side, 0, S.side, MediaQuery.viewInsetsOf(ctx).bottom + S.xl),
          child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.start, children: [
            const Text('What should I call you?', style: T.heading),
            const SizedBox(height: S.lg),
            Panel(
              fill: C.bg,
              padding: const EdgeInsets.symmetric(horizontal: S.lg, vertical: S.md),
              child: TextField(
                controller: c,
                autofocus: true,
                textCapitalization: TextCapitalization.words,
                style: T.body,
                onChanged: (_) => setS(() {}),
                decoration: const InputDecoration(hintText: 'Your name'),
              ),
            ),
            const SizedBox(height: S.lg),
            Align(
              alignment: Alignment.centerRight,
              child: HudButton(label: 'Save', onPressed: dirty ? () => Navigator.pop(ctx, c.text.trim()) : null),
            ),
          ]),
        );
      }),
    );
    c.dispose();
    if (r == null || !context.mounted) return;
    store.updateSettings(store.settings.copyWith(name: r));
    showSaved(context);
  }
}
