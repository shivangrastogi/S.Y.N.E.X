import 'package:flutter/material.dart';

import '../design/theme.dart';
import '../design/tokens.dart';
import '../state/app_settings.dart';

class SettingsScreen extends StatefulWidget {
  const SettingsScreen({super.key, required this.settings});

  final AppSettings settings;

  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  @override
  void initState() {
    super.initState();
    widget.settings.addListener(_onChange);
  }

  @override
  void dispose() {
    widget.settings.removeListener(_onChange);
    super.dispose();
  }

  void _onChange() {
    if (mounted) setState(() {});
  }

  @override
  Widget build(BuildContext context) {
    final p = AerisPalette.of(context);

    return Scaffold(
      appBar: AppBar(
        backgroundColor: p.surface,
        elevation: 0,
        title: Text(
          'SETTINGS',
          style: AerisTheme.readout(context, color: p.ink, size: 13),
        ),
      ),
      body: ListView(
        padding: const EdgeInsets.all(T.s4),
        children: [
          Text('Appearance', style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: T.s1),
          Text(
            'Match your phone, or pick one and stay there.',
            style: Theme.of(context).textTheme.bodySmall,
          ),
          const SizedBox(height: T.s3),
          SegmentedButton<ThemeMode>(
            segments: const [
              ButtonSegment(
                value: ThemeMode.system,
                label: Text('System'),
                icon: Icon(Icons.brightness_auto_outlined, size: 18),
              ),
              ButtonSegment(
                value: ThemeMode.light,
                label: Text('Light'),
                icon: Icon(Icons.light_mode_outlined, size: 18),
              ),
              ButtonSegment(
                value: ThemeMode.dark,
                label: Text('Dark'),
                icon: Icon(Icons.dark_mode_outlined, size: 18),
              ),
            ],
            selected: {widget.settings.themeMode},
            onSelectionChanged: (s) => widget.settings.setThemeMode(s.first),
            showSelectedIcon: false,
          ),
          const SizedBox(height: T.s6),
          Text('Connections', style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: T.s1),
          Text(
            'A.E.R.I.S answers on this phone first. The laptop and cloud tiers '
            'are not built yet, so questions they would handle go unanswered.',
            style: Theme.of(context).textTheme.bodySmall,
          ),
          const SizedBox(height: T.s3),
          Container(
            padding: const EdgeInsets.all(T.s3),
            decoration: BoxDecoration(
              color: p.surface,
              border: Border.all(color: p.line),
              borderRadius: BorderRadius.circular(T.radiusSm),
            ),
            child: Row(
              children: [
                Icon(Icons.laptop_mac, size: 18, color: p.inkDim),
                const SizedBox(width: T.s3),
                Expanded(
                  child: Text(
                    'Laptop — not connected',
                    style: Theme.of(context).textTheme.bodyMedium,
                  ),
                ),
                Text('SOON', style: AerisTheme.readout(context, size: 9.5)),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
