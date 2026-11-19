// Settings — standard Android structure: one overview list, a detail page
// per area. Switches and choices apply immediately and confirm with a
// snackbar; forms (Cloud AI) have an explicit Save that's enabled only when
// something changed, and leaving with unsaved edits asks first.
import 'package:android_intent_plus/android_intent.dart';
import 'package:android_intent_plus/flag.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:permission_handler/permission_handler.dart';

import '../assistant/accessibility_bridge.dart';
import '../core/aeris_log.dart';
import '../brain/brain.dart';
import '../brain/brain_screen.dart';
import '../brain/memory_store.dart';
import '../assistant/cloud_brain.dart';
import '../core/lang.dart';
import '../laptop/pair_screen.dart';
import '../laptop/pairing.dart';
import '../ui/theme.dart';
import '../ui/kit.dart';
import '../wake/wake_controller.dart';

const appVersion = '1.1.0';

class SettingsScreen extends StatefulWidget {
  final bool paired;
  final void Function(Pairing) onPaired;
  final VoidCallback onUnpair;
  const SettingsScreen({super.key, required this.paired, required this.onPaired, required this.onUnpair});

  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> with WidgetsBindingObserver {
  bool _wake = false, _wakeBusy = false;
  int _permIssues = 0;
  bool _cloud = false;
  int _memCount = 0;
  late bool _paired = widget.paired;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    _refresh();
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    super.dispose();
  }

  // Permission screens live in Android Settings — re-check on return.
  @override
  void didChangeAppLifecycleState(AppLifecycleState s) {
    if (s == AppLifecycleState.resumed) _refresh();
  }

  Future<void> _refresh() async {
    final wake = await WakeController.isRunning;
    final perms = await Permissions.check();
    final cloud = await CloudBrain.isConfigured;
    final mem = (await MemoryStore.instance.all()).length;
    if (!mounted) return;
    setState(() {
      _wake = wake;
      _permIssues = perms.where((p) => !p.ok && p.required).length;
      _cloud = cloud;
      _memCount = mem;
    });
  }

  Future<void> _toggleWake(bool on) async {
    setState(() => _wakeBusy = true);
    if (on) {
      if (!await WakeController.start()) {
        if (mounted) showError(context, 'Microphone permission is needed for the wake word');
      }
    } else {
      await WakeController.stop();
    }
    await Future.delayed(const Duration(milliseconds: 500));
    await _refresh();
    if (!mounted) return;
    setState(() => _wakeBusy = false);
    showSaved(context, _wake ? 'Wake word on — say "Aeris"' : 'Wake word off');
  }

  Future<void> _open(Widget page) async {
    await Navigator.of(context).push(MaterialPageRoute(builder: (_) => page));
    _refresh();
  }

  @override
  Widget build(BuildContext context) {
    final lang = switch (Lang.mode.value) {
      LangMode.hinglish => 'Hinglish',
      LangMode.englishIn => 'English (India)',
      LangMode.englishUs => 'English (US)',
    };
    final brain = switch (AerisBrain.instance.mode.value) {
      BrainMode.off => 'Off',
      BrainMode.shadow => 'Shadow',
      BrainMode.on => 'On',
    };
    return PageScaffold(
      title: 'Settings',
      onRefresh: _refresh,
      children: [
        const SizedBox(height: 4),
        Container(
          decoration: BoxDecoration(
            color: A.panel,
            borderRadius: BorderRadius.circular(A.radius),
            border: Border.all(color: A.line),
          ),
          child: Padding(
            padding: const EdgeInsets.fromLTRB(14, 12, 6, 12),
            child: Row(children: [
              AerisOrb(size: 44, online: _wake, active: false),
              const SizedBox(width: 14),
              Expanded(
                child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  const Text('Wake word', style: TextStyle(color: A.text, fontSize: 15, fontWeight: FontWeight.w500)),
                  const SizedBox(height: 3),
                  Text(_wake ? 'Listening for "Aeris" or "Jarvis"' : 'Off — tap the mic to talk',
                      style: const TextStyle(color: A.muted, fontSize: 12)),
                ]),
              ),
              _wakeBusy
                  ? const Padding(
                      padding: EdgeInsets.all(14),
                      child: SizedBox(width: 22, height: 22, child: CircularProgressIndicator(strokeWidth: 2)))
                  : Switch(value: _wake, onChanged: _toggleWake),
            ]),
          ),
        ),
        Section(title: 'Assistant', children: [
          SettingsTile(
              icon: Icons.graphic_eq,
              title: 'Wake word & sensitivity',
              value: _wake ? 'On' : 'Off',
              onTap: () => _open(const WakeWordPage())),
          SettingsTile(
              icon: Icons.translate,
              title: 'Voice & language',
              value: lang,
              onTap: () => _open(const LanguagePage())),
          SettingsTile(
              icon: Icons.memory,
              title: 'On-device brain',
              value: brain,
              onTap: () => _open(const BrainScreen())),
          SettingsTile(
              icon: Icons.cloud_outlined,
              title: 'Cloud AI (Gemini)',
              value: _cloud ? 'Connected' : 'Not set',
              valueColor: _cloud ? A.ok : A.muted,
              onTap: () => _open(const CloudAiPage())),
        ]),
        Section(title: 'Phone', children: [
          SettingsTile(
            icon: Icons.verified_user_outlined,
            title: 'Permissions',
            trailing: _permIssues == 0
                ? const StatusBadge('All set', tone: BadgeTone.ok)
                : StatusBadge('$_permIssues to fix', tone: BadgeTone.warn),
            onTap: () => _open(const PermissionsPage()),
          ),
          SettingsTile(
            icon: Icons.laptop_mac,
            title: 'Laptop link',
            value: _paired ? 'Paired' : 'Not paired',
            valueColor: _paired ? A.ok : A.muted,
            onTap: () => _open(LaptopPage(
              paired: _paired,
              onPaired: (p) {
                widget.onPaired(p);
                setState(() => _paired = true);
              },
              onUnpair: () {
                widget.onUnpair();
                setState(() => _paired = false);
              },
            )),
          ),
        ]),
        Section(title: 'Data & privacy', children: [
          SettingsTile(
              icon: Icons.bookmark_border,
              title: 'Memory',
              value: '$_memCount saved',
              onTap: () => _open(const MemoryPage())),
          SettingsTile(
              icon: Icons.receipt_long_outlined,
              title: 'Logs & diagnostics',
              onTap: () => _open(const DiagnosticsPage())),
        ]),
        Section(children: [
          SettingsTile(icon: Icons.info_outline, title: 'About AERIS', value: appVersion, onTap: () => _open(const AboutPage())),
        ]),
      ],
    );
  }
}

// ── Wake word ─────────────────────────────────────────────────────────
class WakeWordPage extends StatefulWidget {
  const WakeWordPage({super.key});
  @override
  State<WakeWordPage> createState() => _WakeWordPageState();
}

class _WakeWordPageState extends State<WakeWordPage> {
  bool _on = false, _busy = false;
  String _sens = 'balanced';

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    final on = await WakeController.isRunning;
    final s = await WakeController.sensitivity;
    if (mounted) {
      setState(() {
        _on = on;
        _sens = s;
      });
    }
  }

  @override
  Widget build(BuildContext context) => PageScaffold(title: 'Wake word', children: [
        Section(
          footer: 'Wake words: "Aeris", "Hey Aeris" and "Jarvis". Detection runs fully on the phone; '
              'nothing is recorded or sent until AERIS wakes.',
          children: [
            SwitchTile(
              icon: Icons.hearing,
              title: 'Listen for the wake word',
              subtitle: 'Keeps a small notification while on',
              value: _on,
              busy: _busy,
              onChanged: (v) async {
                setState(() => _busy = true);
                var ok = true;
                if (v) {
                  ok = await WakeController.start();
                } else {
                  await WakeController.stop();
                }
                await Future.delayed(const Duration(milliseconds: 500));
                await _load();
                if (!context.mounted) return;
                setState(() => _busy = false);
                ok ? showSaved(context, v ? 'Wake word on' : 'Wake word off') : showError(context, 'Microphone permission needed');
              },
            ),
          ],
        ),
        Section(
          title: 'Sensitivity',
          footer: switch (_sens) {
            'low' => 'Low: almost no false wakes; speak clearly and close to the phone.',
            'high' => 'High: hears you from across the room; may wake by mistake now and then.',
            _ => 'Balanced: recommended for most rooms.',
          },
          children: [
            ChoiceRow<String>(
              options: const [('low', 'Low'), ('balanced', 'Balanced'), ('high', 'High')],
              value: _sens,
              onChanged: (v) async {
                setState(() => _sens = v);
                await WakeController.setSensitivity(v);
                if (context.mounted) showSaved(context, 'Sensitivity set to ${v[0].toUpperCase()}${v.substring(1)}');
              },
            ),
          ],
        ),
      ]);
}

// ── Language ──────────────────────────────────────────────────────────
class LanguagePage extends StatelessWidget {
  const LanguagePage({super.key});

  @override
  Widget build(BuildContext context) {
    const options = [
      (LangMode.hinglish, 'Hinglish', 'Hindi + English mix, Indian voice'),
      (LangMode.englishIn, 'English (India)', 'English only, tuned for an Indian accent'),
      (LangMode.englishUs, 'English (US)', 'English only, US speech model and voice'),
    ];
    return PageScaffold(title: 'Voice & language', children: [
      Section(
        footer: 'Changes how AERIS listens and speaks. Applies from the next sentence.',
        children: [
          ValueListenableBuilder<LangMode>(
            valueListenable: Lang.mode,
            builder: (context, mode, _) => RadioGroup<LangMode>(
              groupValue: mode,
              onChanged: (m) async {
                if (m == null || m == mode) return;
                await Lang.set(m);
                if (context.mounted) {
                  showSaved(context, 'Language: ${options.firstWhere((o) => o.$1 == m).$2}');
                }
              },
              child: Column(children: [
                for (final (v, t, s) in options)
                  RadioListTile<LangMode>(
                    value: v,
                    title: Text(t, style: const TextStyle(fontSize: 14.5)),
                    subtitle: Text(s, style: const TextStyle(color: A.muted, fontSize: 12)),
                  ),
              ]),
            ),
          ),
        ],
      ),
    ]);
  }
}

// ── Cloud AI (a form: explicit Save) ──────────────────────────────────
class CloudAiPage extends StatefulWidget {
  const CloudAiPage({super.key});
  @override
  State<CloudAiPage> createState() => _CloudAiPageState();
}

class _CloudAiPageState extends State<CloudAiPage> {
  static const _models = ['gemini-2.5-flash', 'gemini-2.5-flash-lite', 'gemini-2.5-pro'];
  final _key = TextEditingController();
  final _customModel = TextEditingController();
  String _model = _models.first;
  bool _ground = true, _show = false, _saving = false, _loaded = false;
  // What's stored — dirty = form differs from this.
  String _sKey = '', _sModel = _models.first;
  bool _sGround = true;
  (bool, String, int)? _test;
  bool _testing = false;

  @override
  void initState() {
    super.initState();
    _key.addListener(_changed);
    _customModel.addListener(_changed);
    _load();
  }

  Future<void> _load() async {
    _sKey = await CloudBrain.apiKey;
    _sModel = await CloudBrain.model;
    _sGround = await CloudBrain.grounding;
    _reset();
    setState(() => _loaded = true);
  }

  void _reset() {
    _key.text = _sKey;
    if (_models.contains(_sModel)) {
      _model = _sModel;
      _customModel.text = '';
    } else {
      _model = 'custom';
      _customModel.text = _sModel;
    }
    _ground = _sGround;
    _test = null;
    if (mounted) setState(() {});
  }

  void _changed() => setState(() {});

  String get _modelValue => _model == 'custom' ? _customModel.text.trim() : _model;
  bool get _dirty => _loaded && (_key.text.trim() != _sKey || _modelValue != _sModel || _ground != _sGround);
  String? get _keyError {
    final k = _key.text.trim();
    if (k.isEmpty) return null; // empty = cloud off, allowed
    if (k.contains(' ') || k.length < 20) return 'That doesn\'t look like a Gemini API key';
    return null;
  }

  Future<void> _save() async {
    if (_keyError != null || (_model == 'custom' && _modelValue.isEmpty)) {
      showError(context, _keyError ?? 'Enter a model name');
      return;
    }
    setState(() => _saving = true);
    await CloudBrain.setApiKey(_key.text);
    await CloudBrain.setModel(_modelValue);
    await CloudBrain.setGrounding(_ground);
    _sKey = _key.text.trim();
    _sModel = _modelValue;
    _sGround = _ground;
    if (!mounted) return;
    setState(() => _saving = false);
    showSaved(context, _sKey.isEmpty ? 'Cloud AI turned off' : 'Cloud AI settings saved');
  }

  Future<void> _runTest() async {
    FocusScope.of(context).unfocus();
    setState(() {
      _testing = true;
      _test = null;
    });
    final r = await CloudBrain.test(_key.text, _modelValue, ground: _ground);
    if (mounted) {
      setState(() {
        _testing = false;
        _test = r;
      });
    }
  }

  @override
  void dispose() {
    _key.dispose();
    _customModel.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return UnsavedChangesGuard(
      dirty: _dirty,
      saving: _saving,
      onSave: _save,
      onDiscard: _reset,
      child: PageScaffold(
        title: 'Cloud AI',
        actions: [
          Padding(
            padding: const EdgeInsets.only(right: 12),
            child: FilledButton(
              style: FilledButton.styleFrom(minimumSize: const Size(72, 38)),
              onPressed: _dirty && !_saving ? _save : null,
              child: const Text('Save'),
            ),
          ),
        ],
        children: [
          const Padding(
            padding: EdgeInsets.fromLTRB(4, 8, 4, 0),
            child: Text(
                'Used for web answers and the phone agent when the laptop is off. The key is stored '
                'encrypted on this phone only.',
                style: TextStyle(color: A.muted, fontSize: 13, height: 1.5)),
          ),
          const SizedBox(height: 20),
          TextField(
            controller: _key,
            obscureText: !_show,
            autocorrect: false,
            enableSuggestions: false,
            style: const TextStyle(fontFamily: A.mono, fontSize: 13),
            decoration: InputDecoration(
              labelText: 'Gemini API key',
              helperText: 'Free at aistudio.google.com → Get API key',
              errorText: _keyError,
              suffixIcon: Row(mainAxisSize: MainAxisSize.min, children: [
                IconButton(
                  tooltip: 'Paste',
                  icon: const Icon(Icons.content_paste, size: 18),
                  onPressed: () async {
                    final d = await Clipboard.getData(Clipboard.kTextPlain);
                    if (d?.text != null) _key.text = d!.text!.trim();
                  },
                ),
                IconButton(
                  tooltip: _show ? 'Hide' : 'Show',
                  icon: Icon(_show ? Icons.visibility_off : Icons.visibility, size: 18),
                  onPressed: () => setState(() => _show = !_show),
                ),
              ]),
            ),
          ),
          const SizedBox(height: 16),
          DropdownButtonFormField<String>(
            initialValue: _model,
            decoration: const InputDecoration(labelText: 'Model'),
            dropdownColor: A.panelHi,
            items: [
              for (final m in _models)
                DropdownMenuItem(value: m, child: Text(m == _models.first ? '$m (free, fast)' : m)),
              const DropdownMenuItem(value: 'custom', child: Text('Custom…')),
            ],
            onChanged: (v) => setState(() => _model = v!),
          ),
          if (_model == 'custom') ...[
            const SizedBox(height: 12),
            TextField(
              controller: _customModel,
              style: const TextStyle(fontFamily: A.mono, fontSize: 13),
              decoration: const InputDecoration(labelText: 'Model name', hintText: 'e.g. gemini-3-flash'),
            ),
          ],
          Section(children: [
            SwitchTile(
              title: 'Live web results',
              subtitle: 'Google Search grounding. Falls back to a plain answer if your key doesn\'t allow it.',
              value: _ground,
              onChanged: (v) => setState(() => _ground = v),
            ),
          ]),
          const SizedBox(height: 16),
          Row(children: [
            OutlinedButton.icon(
              onPressed: _testing ? null : _runTest,
              icon: _testing
                  ? const SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2))
                  : const Icon(Icons.bolt, size: 18),
              label: const Text('Test connection'),
            ),
            const SizedBox(width: 12),
            if (_test != null)
              Expanded(
                child: Text(
                  _test!.$1 ? '✓ Works · ${(_test!.$3 / 1000).toStringAsFixed(1)} s' : _test!.$2,
                  maxLines: 3,
                  overflow: TextOverflow.ellipsis,
                  style: TextStyle(color: _test!.$1 ? A.ok : A.hot, fontSize: 12.5),
                ),
              ),
          ]),
          const SizedBox(height: 4),
          const Text('Tests what\'s typed above — nothing is saved until you tap Save.',
              style: TextStyle(color: A.faint, fontSize: 11.5)),
          if (_sKey.isNotEmpty) ...[
            const SizedBox(height: 24),
            Section(children: [
              SettingsTile(
                icon: Icons.delete_outline,
                title: 'Remove key',
                destructive: true,
                chevron: false,
                onTap: () async {
                  if (await confirm(context,
                      title: 'Remove the Gemini key?',
                      body: 'Web answers and the phone agent will stop working until you add a key again.',
                      action: 'Remove',
                      destructive: true)) {
                    await CloudBrain.setApiKey('');
                    _sKey = '';
                    _reset();
                    if (context.mounted) showSaved(context, 'Key removed');
                  }
                },
              ),
            ]),
          ],
          const SizedBox(height: 80), // room for the unsaved-changes bar
        ],
      ),
    );
  }
}

// ── Permissions ───────────────────────────────────────────────────────
class PermissionItem {
  final String title, why;
  final bool ok, required;
  final Future<void> Function() fix;
  const PermissionItem(this.title, this.why, this.ok, this.fix, {this.required = true});
}

class Permissions {
  static Future<List<PermissionItem>> check() async => [
        PermissionItem('Microphone', 'To hear you', await Permission.microphone.isGranted,
            () async => (await Permission.microphone.request()).isPermanentlyDenied ? await openAppSettings() : null),
        PermissionItem('Notifications', 'Keeps the wake word alive in the background',
            await WakeController.notificationsOk, WakeController.requestNotifications),
        PermissionItem('Battery: unrestricted', 'Otherwise Android stops AERIS to save power',
            await WakeController.batteryExempt, WakeController.requestBatteryExempt),
        PermissionItem('Display over other apps', 'So AERIS can appear when you say its name',
            await WakeController.canOverlay, WakeController.requestOverlay),
        PermissionItem('Contacts', 'To call and message people by name', await Permission.contacts.isGranted,
            () async => (await Permission.contacts.request()).isPermanentlyDenied ? await openAppSettings() : null),
        PermissionItem('Screen control', 'Read the screen, tap, scroll, run multi-step tasks',
            await AccessibilityBridge.isEnabled(), AccessibilityBridge.openSettings,
            required: false),
      ];
}

class PermissionsPage extends StatefulWidget {
  const PermissionsPage({super.key});
  @override
  State<PermissionsPage> createState() => _PermissionsPageState();
}

class _PermissionsPageState extends State<PermissionsPage> with WidgetsBindingObserver {
  List<PermissionItem> _items = const [];

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    _load();
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState s) {
    if (s == AppLifecycleState.resumed) _load();
  }

  Future<void> _load() async {
    final items = await Permissions.check();
    if (mounted) setState(() => _items = items);
  }

  Widget _row(PermissionItem p) => SettingsTile(
        icon: p.ok ? Icons.check_circle : (p.required ? Icons.error_outline : Icons.radio_button_unchecked),
        title: p.title,
        subtitle: p.why,
        trailing: p.ok
            ? const StatusBadge('Allowed', tone: BadgeTone.ok)
            : TextButton(
                onPressed: () async {
                  await p.fix();
                  await _load();
                },
                child: const Text('Allow')),
      );

  @override
  Widget build(BuildContext context) => PageScaffold(title: 'Permissions', onRefresh: _load, children: [
        Section(title: 'Needed', children: [for (final p in _items.where((p) => p.required)) _row(p)]),
        Section(
          title: 'Optional',
          footer: 'Screen control uses Android Accessibility. AERIS only acts when you ask, and asks '
              'before anything that sends a message or spends money.',
          children: [for (final p in _items.where((p) => !p.required)) _row(p)],
        ),
        Section(
          title: 'Realme / ColorOS',
          footer: 'These phones also need two manual switches, or the wake word dies in the background.',
          children: [
            SettingsTile(
              icon: Icons.open_in_new,
              title: 'Pop-up windows in background',
              subtitle: 'App info → Permissions → "Display pop-up windows while running in background"',
              onTap: openAppSettings,
            ),
            SettingsTile(
              icon: Icons.open_in_new,
              title: 'Auto launch',
              subtitle: 'App info → Battery → "Allow auto launch" and "Allow background activity"',
              onTap: openAppSettings,
            ),
            SettingsTile(
              icon: Icons.assistant_outlined,
              title: 'Make AERIS the default assistant',
              subtitle: 'Then holding the power button opens AERIS',
              onTap: () => const AndroidIntent(
                      action: 'android.settings.VOICE_INPUT_SETTINGS', flags: [Flag.FLAG_ACTIVITY_NEW_TASK])
                  .launch(),
            ),
          ],
        ),
      ]);
}

// ── Laptop ────────────────────────────────────────────────────────────
class LaptopPage extends StatefulWidget {
  final bool paired;
  final void Function(Pairing) onPaired;
  final VoidCallback onUnpair;
  const LaptopPage({super.key, required this.paired, required this.onPaired, required this.onUnpair});
  @override
  State<LaptopPage> createState() => _LaptopPageState();
}

class _LaptopPageState extends State<LaptopPage> {
  late bool _paired = widget.paired;

  @override
  Widget build(BuildContext context) => PageScaffold(title: 'Laptop link', children: [
        Section(
          footer: 'Optional. A linked laptop runs heavier commands, mirrors its screen to the phone and '
              'shares files and clipboard. Everything between them is end-to-end encrypted.',
          children: [
            SettingsTile(
              icon: Icons.laptop_mac,
              title: _paired ? 'Laptop paired' : 'No laptop linked',
              trailing: StatusBadge(_paired ? 'Paired' : 'Off', tone: _paired ? BadgeTone.ok : BadgeTone.neutral),
            ),
          ],
        ),
        Section(children: [
          if (!_paired)
            SettingsTile(
              icon: Icons.qr_code_scanner,
              title: 'Pair with a laptop',
              subtitle: 'Scan the QR code shown by AERIS on the PC',
              onTap: () => Navigator.of(context).push(MaterialPageRoute(
                  builder: (ctx) => PairScreen(onPaired: (p) {
                        widget.onPaired(p);
                        setState(() => _paired = true);
                        Navigator.of(ctx).pop();
                        showSaved(context, 'Laptop paired');
                      }))),
            )
          else
            SettingsTile(
              icon: Icons.link_off,
              title: 'Unpair this laptop',
              destructive: true,
              chevron: false,
              onTap: () async {
                if (await confirm(context,
                    title: 'Unpair the laptop?',
                    body: 'The phone forgets the encryption key. You can pair again any time by scanning the QR.',
                    action: 'Unpair',
                    destructive: true)) {
                  widget.onUnpair();
                  setState(() => _paired = false);
                  if (context.mounted) showSaved(context, 'Laptop unpaired');
                }
              },
            ),
        ]),
      ]);
}

// ── Memory ────────────────────────────────────────────────────────────
class MemoryPage extends StatefulWidget {
  const MemoryPage({super.key});
  @override
  State<MemoryPage> createState() => _MemoryPageState();
}

class _MemoryPageState extends State<MemoryPage> {
  List<MemoryItem> _items = const [];

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    final all = await MemoryStore.instance.all();
    if (mounted) setState(() => _items = all.reversed.toList());
  }

  Future<void> _delete(MemoryItem m) async {
    final all = await MemoryStore.instance.all();
    final index = all.indexOf(m);
    await MemoryStore.instance.remove(m);
    await _load();
    if (!mounted) return;
    ScaffoldMessenger.of(context)
      ..hideCurrentSnackBar()
      ..showSnackBar(SnackBar(
        content: const Text('Deleted'),
        action: SnackBarAction(
            label: 'Undo',
            onPressed: () async {
              await MemoryStore.instance.restore(m, index);
              _load();
            }),
      ));
  }

  @override
  Widget build(BuildContext context) {
    final facts = _items.where((m) => m.kind == 'fact').toList();
    final notes = _items.where((m) => m.kind == 'note').toList();
    Widget row(MemoryItem m) => SettingsTile(
          title: m.text,
          subtitle: '${m.at.day}/${m.at.month}/${m.at.year}',
          trailing: IconButton(
              tooltip: 'Delete', icon: const Icon(Icons.close, size: 18, color: A.faint), onPressed: () => _delete(m)),
        );
    return PageScaffold(
      title: 'Memory',
      actions: [
        if (_items.isNotEmpty)
          IconButton(
            tooltip: 'Delete all',
            icon: const Icon(Icons.delete_sweep_outlined),
            onPressed: () async {
              if (await confirm(context,
                  title: 'Delete all memory?',
                  body: 'Removes ${_items.length} saved facts and notes from this phone. This can\'t be undone.',
                  action: 'Delete all',
                  destructive: true)) {
                await MemoryStore.instance.clear();
                await _load();
                if (context.mounted) showSaved(context, 'Memory cleared');
              }
            },
          ),
      ],
      children: [
        if (_items.isEmpty)
          const Padding(
            padding: EdgeInsets.only(top: 60),
            child: Column(children: [
              Icon(Icons.bookmark_border, color: A.faint, size: 40),
              SizedBox(height: 12),
              Text('Nothing saved yet', style: TextStyle(color: A.text, fontSize: 15)),
              SizedBox(height: 6),
              Text('Say "yaad rakho, my locker code is 4412"\nor "note: buy milk".',
                  textAlign: TextAlign.center, style: TextStyle(color: A.muted, fontSize: 13, height: 1.5)),
            ]),
          ),
        if (facts.isNotEmpty) Section(title: 'Things I remember', children: [for (final m in facts) row(m)]),
        if (notes.isNotEmpty) Section(title: 'Notes', children: [for (final m in notes) row(m)]),
        if (_items.isNotEmpty)
          const Padding(
            padding: EdgeInsets.fromLTRB(4, 10, 4, 0),
            child: Text('Stored only on this phone.', style: TextStyle(color: A.faint, fontSize: 12)),
          ),
      ],
    );
  }
}

// ── Diagnostics ───────────────────────────────────────────────────────
class DiagnosticsPage extends StatelessWidget {
  const DiagnosticsPage({super.key});

  @override
  Widget build(BuildContext context) => PageScaffold(title: 'Logs & diagnostics', children: [
        Section(children: [
          SettingsTile(
            icon: Icons.bug_report_outlined,
            title: 'Error log',
            subtitle: 'Things that failed silently',
            onTap: () => Navigator.of(context).push(MaterialPageRoute(builder: (_) => const _ErrorLogPage())),
          ),
          SettingsTile(
            icon: Icons.copy_all,
            title: 'Copy brain decisions',
            subtitle: 'Every on-device brain decision, as JSON lines — for training the next version',
            chevron: false,
            onTap: () async {
              final f = await AerisBrain.instance.logFile();
              if (!await f.exists()) {
                if (context.mounted) showError(context, 'No brain decisions logged yet');
                return;
              }
              final lines = await f.readAsLines();
              await Clipboard.setData(ClipboardData(text: lines.join('\n')));
              if (context.mounted) showSaved(context, 'Copied ${lines.length} decisions');
            },
          ),
          SettingsTile(
            icon: Icons.delete_outline,
            title: 'Clear brain log',
            destructive: true,
            chevron: false,
            onTap: () async {
              if (await confirm(context,
                  title: 'Clear the brain log?',
                  body: 'Deletes the recorded decisions. Export them first if you want them for training.',
                  action: 'Clear',
                  destructive: true)) {
                final f = await AerisBrain.instance.logFile();
                if (await f.exists()) await f.delete();
                if (context.mounted) showSaved(context, 'Brain log cleared');
              }
            },
          ),
        ]),
      ]);
}

class _ErrorLogPage extends StatelessWidget {
  const _ErrorLogPage();

  @override
  Widget build(BuildContext context) => Scaffold(
        appBar: AppBar(title: const Text('Error log'), actions: [
          IconButton(
            tooltip: 'Copy',
            icon: const Icon(Icons.copy),
            onPressed: () {
              Clipboard.setData(ClipboardData(text: AerisLog.lines.value.join('\n')));
              showSaved(context, 'Copied');
            },
          ),
          IconButton(
            tooltip: 'Clear',
            icon: const Icon(Icons.delete_outline),
            onPressed: () async {
              if (await confirm(context, title: 'Clear the error log?', body: 'This only clears the list on screen.', action: 'Clear')) {
                AerisLog.clear();
              }
            },
          ),
        ]),
        body: ValueListenableBuilder<List<String>>(
          valueListenable: AerisLog.lines,
          builder: (_, lines, __) => lines.isEmpty
              ? const Center(child: Text('No errors recorded', style: TextStyle(color: A.muted)))
              : ListView.separated(
                  padding: const EdgeInsets.all(16),
                  itemCount: lines.length,
                  separatorBuilder: (_, __) => const Divider(height: 16),
                  itemBuilder: (_, i) => SelectableText(lines[lines.length - 1 - i],
                      style: const TextStyle(fontFamily: A.mono, fontSize: 12, color: A.text)),
                ),
        ),
      );
}

// ── About ─────────────────────────────────────────────────────────────
class AboutPage extends StatelessWidget {
  const AboutPage({super.key});

  @override
  Widget build(BuildContext context) => PageScaffold(title: 'About', children: [
        const SizedBox(height: 20),
        const Center(child: AerisOrb(size: 120, online: true)),
        const SizedBox(height: 16),
        const Center(child: Text('AERIS', style: TextStyle(fontSize: 22, fontWeight: FontWeight.w500, letterSpacing: 4))),
        const Center(child: Text('version $appVersion', style: TextStyle(fontFamily: A.mono, color: A.faint, fontSize: 12))),
        Section(title: 'How a command is handled', children: [
          for (final (t, s) in const [
            ('1 · Wake', 'An on-device keyword spotter hears "Aeris" or "Jarvis".'),
            ('2 · Listen', 'Google speech recognition turns your voice into text.'),
            ('3 · Decide', 'The on-device brain (or rules) picks the action. Nothing leaves the phone.'),
            ('4 · Act', 'Phone actions run directly; multi-app tasks use screen control.'),
            ('5 · Escalate', 'Knowledge or live questions go to the laptop or Gemini, if set up.'),
          ])
            SettingsTile(title: t, subtitle: s),
        ]),
        Section(title: 'Licences', children: [
          SettingsTile(
            title: 'Open-source licences',
            onTap: () => showLicensePage(context: context, applicationName: 'AERIS', applicationVersion: appVersion),
          ),
        ]),
      ]);
}
