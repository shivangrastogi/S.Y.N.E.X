// Assistant settings — the one-time setup for the always-on "Aeris" hotword:
// the on/off toggle and the keep-alive checklist that stops ColorOS (Realme)
// from killing the service. No accounts/keys — the wake engine is the
// bundled open-source sherpa-onnx keyword spotter.
import 'package:flutter/material.dart';
import 'package:permission_handler/permission_handler.dart';
import 'package:android_intent_plus/android_intent.dart';
import 'package:android_intent_plus/flag.dart';
import 'theme.dart';
import 'wake_controller.dart';
import 'cloud_brain.dart';
import 'accessibility_bridge.dart';
import 'aeris_log.dart';

class AssistantSettingsScreen extends StatefulWidget {
  const AssistantSettingsScreen({super.key});
  @override
  State<AssistantSettingsScreen> createState() =>
      _AssistantSettingsScreenState();
}

class _AssistantSettingsScreenState extends State<AssistantSettingsScreen> {
  bool _running = false;
  bool _battery = false;
  bool _overlay = false;
  bool _notifs = false;
  bool _a11y = false;
  bool _busy = false;
  String _sensitivity = 'balanced';
  // Tier-3 cloud brain (Gemini).
  final _geminiKey = TextEditingController();
  final _geminiModel = TextEditingController();
  bool _grounding = true;
  bool _testing = false;
  String _testResult = '';

  @override
  void initState() {
    super.initState();
    _refresh();
    _loadCloud();
  }

  Future<void> _loadCloud() async {
    final k = await CloudBrain.apiKey;
    final m = await CloudBrain.model;
    final g = await CloudBrain.grounding;
    if (!mounted) return;
    setState(() {
      if (_geminiKey.text.isEmpty) _geminiKey.text = k;
      if (_geminiModel.text.isEmpty) _geminiModel.text = m;
      _grounding = g;
    });
  }

  Future<void> _testCloud() async {
    await CloudBrain.setApiKey(_geminiKey.text);
    await CloudBrain.setModel(_geminiModel.text);
    await CloudBrain.setGrounding(_grounding);
    setState(() {
      _testing = true;
      _testResult = '';
    });
    final ans = await CloudBrain.ask('Ek line mein khud ko introduce karo.');
    if (!mounted) return;
    setState(() {
      _testing = false;
      _testResult = ans;
    });
  }

  Future<void> _refresh() async {
    final running = await WakeController.isRunning;
    final battery = await WakeController.batteryExempt;
    final overlay = await WakeController.canOverlay;
    final notifs = await WakeController.notificationsOk;
    final a11y = await AccessibilityBridge.isEnabled();
    final sens = await WakeController.sensitivity;
    if (!mounted) return;
    setState(() {
      _running = running;
      _battery = battery;
      _overlay = overlay;
      _notifs = notifs;
      _a11y = a11y;
      _sensitivity = sens;
    });
  }

  Future<void> _toggle() async {
    setState(() => _busy = true);
    if (_running) {
      await WakeController.stop();
    } else {
      final ok = await WakeController.start();
      if (!ok) _snack('Mic permission chahiye');
    }
    await Future.delayed(const Duration(milliseconds: 600));
    await _refresh();
    if (mounted) setState(() => _busy = false);
  }

  void _snack(String msg) {
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(
      backgroundColor: A.panelHi,
      content: Text(msg, style: const TextStyle(color: A.text)),
    ));
  }

  Widget _check(String title, String sub, bool done, VoidCallback onFix) {
    return ListTile(
      leading: Icon(done ? Icons.check_circle : Icons.error_outline,
          color: done ? A.plasmaC : A.hot),
      title: Text(title, style: const TextStyle(color: A.text, fontSize: 15)),
      subtitle:
          Text(sub, style: const TextStyle(color: A.muted, fontSize: 12)),
      trailing: done
          ? null
          : TextButton(onPressed: onFix, child: const Text('Fix')),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        backgroundColor: A.deck,
        title: const Text('Assistant settings',
            style: TextStyle(color: A.text, fontSize: 17)),
        iconTheme: const IconThemeData(color: A.muted),
      ),
      body: RefreshIndicator(
        onRefresh: _refresh,
        child: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            // ── Hotword on/off ────────────────────────────────────────
            Container(
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: A.panel,
                borderRadius: BorderRadius.circular(16),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(children: [
                    Icon(Icons.mic,
                        color: _running ? A.plasmaC : A.faint, size: 20),
                    const SizedBox(width: 8),
                    Expanded(
                      child: Text(
                        _running
                            ? 'AERIS sun raha hai'
                            : 'Always-on hotword band hai',
                        style: const TextStyle(
                            color: A.text,
                            fontSize: 15,
                            fontWeight: FontWeight.w600),
                      ),
                    ),
                    _busy
                        ? const SizedBox(
                            width: 20,
                            height: 20,
                            child: CircularProgressIndicator(strokeWidth: 2))
                        : Switch(value: _running, onChanged: (_) => _toggle()),
                  ]),
                  const SizedBox(height: 10),
                  const Text(
                    'Wake words: "Aeris" / "Hey Aeris" (aur "Jarvis" bhi). '
                    'Sab kuch on-device, free, koi account nahi.',
                    style: TextStyle(color: A.faint, fontSize: 12),
                  ),
                  const SizedBox(height: 14),
                  // A11: tune without a rebuild. Changing it restarts the
                  // wake service so the new operating point applies live.
                  const Text('SENSITIVITY',
                      style: TextStyle(
                          color: A.faint,
                          fontSize: 10,
                          fontFamily: A.mono,
                          letterSpacing: 1.5)),
                  const SizedBox(height: 8),
                  Row(
                    children: [
                      for (final (v, label, hint) in const [
                        ('low', 'Low', 'zero false wakes'),
                        ('balanced', 'Balanced', 'recommended'),
                        ('high', 'High', 'door se bhi sune'),
                      ]) ...[
                        Expanded(
                          child: GestureDetector(
                            onTap: () async {
                              setState(() => _sensitivity = v);
                              await WakeController.setSensitivity(v);
                              _snack('Sensitivity: $label — $hint');
                            },
                            child: Container(
                              padding:
                                  const EdgeInsets.symmetric(vertical: 9),
                              decoration: BoxDecoration(
                                borderRadius: BorderRadius.circular(10),
                                color: _sensitivity == v
                                    ? A.plasmaB.withValues(alpha: 0.16)
                                    : Colors.transparent,
                                border: Border.all(
                                    color: _sensitivity == v
                                        ? A.plasmaB
                                        : A.line),
                              ),
                              child: Text(label,
                                  textAlign: TextAlign.center,
                                  style: TextStyle(
                                      color: _sensitivity == v
                                          ? A.plasmaB
                                          : A.muted,
                                      fontSize: 12,
                                      fontWeight: FontWeight.w600)),
                            ),
                          ),
                        ),
                        if (v != 'high') const SizedBox(width: 8),
                      ],
                    ],
                  ),
                ],
              ),
            ),
            const SizedBox(height: 20),
            // ── Keep-alive checklist (Realme/ColorOS survival) ────────
            const Padding(
              padding: EdgeInsets.only(left: 4, bottom: 4),
              child: Text('BACKGROUND MEIN ZINDA RAKHNE KE LIYE',
                  style: TextStyle(
                      color: A.faint,
                      fontSize: 11,
                      fontFamily: A.mono,
                      letterSpacing: 1.2)),
            ),
            Container(
              decoration: BoxDecoration(
                color: A.panel,
                borderRadius: BorderRadius.circular(16),
              ),
              child: Column(children: [
                _check(
                    'Notifications',
                    'Service ki permanent notification ke liye',
                    _notifs, () async {
                  await WakeController.requestNotifications();
                  _refresh();
                }),
                _check(
                    'Battery — Don\'t optimize',
                    'Warna Doze mode service maar dega',
                    _battery, () async {
                  await WakeController.requestBatteryExempt();
                  _refresh();
                }),
                _check(
                    'Display over other apps',
                    '"Aeris" bolne pe app screen pe aa sake',
                    _overlay, () async {
                  await WakeController.requestOverlay();
                  _refresh();
                }),
                const ListTile(
                  leading: Icon(Icons.open_in_new, color: A.hot),
                  title: Text('Background pop-up  ⚠ ZAROORI',
                      style: TextStyle(color: A.text, fontSize: 15)),
                  subtitle: Text(
                      'Realme: App info → Permissions → "Display pop-up '
                      'windows while running in background" → Allow.\n'
                      'ISKE BINA home screen pe wake pe UI nahi aayegi.',
                      style: TextStyle(color: A.muted, fontSize: 12)),
                  trailing: TextButton(
                      onPressed: openAppSettings, child: Text('Open')),
                ),
                const ListTile(
                  leading: Icon(Icons.rocket_launch, color: A.plasmaB),
                  title: Text('Realme autostart (manual)',
                      style: TextStyle(color: A.text, fontSize: 15)),
                  subtitle: Text(
                      'App info → Battery → "Allow auto launch" +\n'
                      '"Allow background activity" ON karo',
                      style: TextStyle(color: A.muted, fontSize: 12)),
                  trailing: TextButton(
                      onPressed: openAppSettings, child: Text('Open')),
                ),
              ]),
            ),
            const SizedBox(height: 20),
            // ── Phase A5/A6: screen control + assistant role ──────────
            const Padding(
              padding: EdgeInsets.only(left: 4, bottom: 4),
              child: Text('POORA PHONE CONTROL (OPTIONAL)',
                  style: TextStyle(
                      color: A.faint,
                      fontSize: 11,
                      fontFamily: A.mono,
                      letterSpacing: 1.2)),
            ),
            Container(
              decoration: BoxDecoration(
                color: A.panel,
                borderRadius: BorderRadius.circular(16),
              ),
              child: Column(children: [
                _check(
                    'Screen control',
                    'Screen padhna/summarise, tap, scroll, back/home',
                    _a11y, () async {
                  await AccessibilityBridge.openSettings();
                }),
                ListTile(
                  leading: const Icon(Icons.assistant, color: A.plasmaB),
                  title: const Text('Default assistant banao',
                      style: TextStyle(color: A.text, fontSize: 15)),
                  subtitle: const Text(
                      'Settings → Default apps → Digital assistant → AERIS.\n'
                      'Phir power-button dabaye rakho = AERIS sunega.',
                      style: TextStyle(color: A.muted, fontSize: 12)),
                  trailing: TextButton(
                      onPressed: () {
                        const AndroidIntent(
                            action:
                                'android.settings.VOICE_INPUT_SETTINGS',
                            flags: [Flag.FLAG_ACTIVITY_NEW_TASK]).launch();
                      },
                      child: const Text('Open')),
                ),
              ]),
            ),
            const SizedBox(height: 20),
            // ── Tier-3 cloud brain (Gemini) ───────────────────────────
            const Padding(
              padding: EdgeInsets.only(left: 4, bottom: 4),
              child: Text('CLOUD BRAIN (LAPTOP OFF HONE PE WEB ANSWERS)',
                  style: TextStyle(
                      color: A.faint,
                      fontSize: 11,
                      fontFamily: A.mono,
                      letterSpacing: 1.2)),
            ),
            Container(
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: A.panel,
                borderRadius: BorderRadius.circular(16),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  TextField(
                    controller: _geminiKey,
                    obscureText: true,
                    style: const TextStyle(
                        color: A.text, fontFamily: A.mono, fontSize: 12),
                    decoration: const InputDecoration(
                      labelText: 'Gemini API key',
                      labelStyle: TextStyle(color: A.muted),
                      helperText: 'Free: aistudio.google.com → Get API key. '
                          'Koi card nahi.',
                      helperStyle: TextStyle(color: A.faint, fontSize: 11),
                      border: OutlineInputBorder(),
                    ),
                    onChanged: (v) => CloudBrain.setApiKey(v),
                  ),
                  const SizedBox(height: 12),
                  TextField(
                    controller: _geminiModel,
                    style: const TextStyle(
                        color: A.text, fontFamily: A.mono, fontSize: 12),
                    decoration: const InputDecoration(
                      labelText: 'Model',
                      labelStyle: TextStyle(color: A.muted),
                      helperText: 'Default gemini-2.5-flash (free). Live web '
                          'ke liye Gemini 3.x + grounding.',
                      helperStyle: TextStyle(color: A.faint, fontSize: 11),
                      helperMaxLines: 2,
                      border: OutlineInputBorder(),
                    ),
                    onChanged: (v) => CloudBrain.setModel(v),
                  ),
                  SwitchListTile(
                    contentPadding: EdgeInsets.zero,
                    value: _grounding,
                    onChanged: (v) {
                      setState(() => _grounding = v);
                      CloudBrain.setGrounding(v);
                    },
                    title: const Text('Live web (grounding)',
                        style: TextStyle(color: A.text, fontSize: 14)),
                    subtitle: const Text(
                        'Free key pe na chale to khud plain answer de dega',
                        style: TextStyle(color: A.faint, fontSize: 11)),
                  ),
                  Row(children: [
                    TextButton.icon(
                      onPressed: _testing ? null : _testCloud,
                      icon: _testing
                          ? const SizedBox(
                              width: 16,
                              height: 16,
                              child: CircularProgressIndicator(strokeWidth: 2))
                          : const Icon(Icons.bolt, size: 18),
                      label: const Text('Test'),
                    ),
                    if (_testResult.isNotEmpty)
                      Expanded(
                        child: Text(_testResult,
                            style: const TextStyle(
                                color: A.plasmaC, fontSize: 12)),
                      ),
                  ]),
                ],
              ),
            ),
            const SizedBox(height: 20),
            // A9: surface the in-app error log so failures aren't invisible.
            Container(
              decoration: BoxDecoration(
                color: A.panel,
                borderRadius: BorderRadius.circular(16),
              ),
              child: ListTile(
                leading: const Icon(Icons.bug_report_outlined, color: A.muted),
                title: const Text('Error log',
                    style: TextStyle(color: A.text, fontSize: 15)),
                subtitle: const Text('Kya fail hua — dekho (silent errors)',
                    style: TextStyle(color: A.muted, fontSize: 12)),
                trailing: const Icon(Icons.chevron_right, color: A.faint),
                onTap: () => Navigator.of(context).push(MaterialPageRoute(
                    builder: (_) => const _LogsScreen())),
              ),
            ),
            const SizedBox(height: 20),
            Container(
              padding: const EdgeInsets.all(14),
              decoration: BoxDecoration(
                color: A.panel.withValues(alpha: 0.6),
                borderRadius: BorderRadius.circular(12),
              ),
              child: const Text(
                'Kaise chalta hai: wake word (sherpa-onnx, on-device) sirf '
                '"Aeris" pakadta hai — uske baad wahi Google en-IN STT '
                'sunta hai jo hold-to-talk mein hai. Reply ke baad follow-up '
                'window milti hai. Command pehle phone khud try karta hai '
                '(torch/call/app), phir laptop, aur laptop off ho to cloud '
                'brain (Gemini). "Aeris sleep" ya "so jao" bolo to sona.',
                style: TextStyle(color: A.faint, fontSize: 12, height: 1.5),
              ),
            ),
          ],
        ),
      ),
    );
  }

  @override
  void dispose() {
    _geminiKey.dispose();
    _geminiModel.dispose();
    super.dispose();
  }
}

// A9: a simple viewer over the in-app error/event ring buffer.
class _LogsScreen extends StatelessWidget {
  const _LogsScreen();

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        backgroundColor: A.deck,
        iconTheme: const IconThemeData(color: A.muted),
        title: const Text('Error log',
            style: TextStyle(color: A.text, fontSize: 17)),
        actions: const [
          IconButton(
            icon: Icon(Icons.delete_outline, color: A.muted),
            onPressed: AerisLog.clear,
          ),
        ],
      ),
      body: ValueListenableBuilder<List<String>>(
        valueListenable: AerisLog.lines,
        builder: (_, lines, __) {
          if (lines.isEmpty) {
            return const Center(
              child: Text('Abhi tak koi error nahi 🎉',
                  style: TextStyle(color: A.muted)),
            );
          }
          return ListView.builder(
            padding: const EdgeInsets.all(12),
            itemCount: lines.length,
            itemBuilder: (_, i) {
              final line = lines[lines.length - 1 - i]; // newest first
              return Padding(
                padding: const EdgeInsets.symmetric(vertical: 4),
                child: SelectableText(
                  line,
                  style: const TextStyle(
                      color: A.text, fontFamily: A.mono, fontSize: 12),
                ),
              );
            },
          );
        },
      ),
    );
  }
}
