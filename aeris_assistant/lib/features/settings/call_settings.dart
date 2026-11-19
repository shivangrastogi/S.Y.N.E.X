import 'package:flutter/material.dart';
import 'package:permission_handler/permission_handler.dart';

import '../../app/scope.dart';
import '../../ui/kit/controls.dart';
import '../../ui/tokens.dart';
import 'permission_row.dart';

/// Settings → Calls: the "answer calls by voice" switch and what it needs.
class CallSettingsSection extends StatelessWidget {
  const CallSettingsSection({super.key});

  /// Asked in this order when the switch is turned on. Phone access is the
  /// only must-have; the rest make it nicer (glow, SMS) or more reliable.
  static const _requirements = [
    (Icons.phone_in_talk_outlined, 'Phone', 'See who is calling, answer and decline', Permission.phone),
    (Icons.notifications_none_rounded, 'Notifications', 'The small "AERIS is ready" notification', Permission.notification),
    (Icons.blur_on_rounded, 'Display over other apps', 'The edge glow while AERIS listens', Permission.systemAlertWindow),
    (Icons.sms_outlined, 'SMS', '"Call you later" text after you decline', Permission.sms),
    (Icons.battery_saver_outlined, 'No battery limits', 'So the phone doesn\'t stop AERIS in the background', Permission.ignoreBatteryOptimizations),
  ];

  Future<void> _turnOn(BuildContext context) async {
    for (final (_, _, _, permission) in _requirements) {
      if (!await permission.isGranted) await permission.request();
    }
    if (!context.mounted) return;
    if (!await Permission.phone.isGranted) {
      if (context.mounted) showSaved(context, 'Phone access is needed for this');
      return;
    }
    if (!context.mounted) return;
    await _save(context, true);
  }

  Future<void> _save(BuildContext context, bool enabled) async {
    final store = context.store;
    store.updateSettings(store.settings.copyWith(callsByVoice: enabled));
    await context.calls?.applySetting();
    if (context.mounted) showSaved(context, enabled ? 'AERIS will answer calls by voice' : 'Calls by voice off');
  }

  @override
  Widget build(BuildContext context) {
    final enabled = context.store.settings.callsByVoice;
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      RowGroup(children: [
        SettingRow(
          icon: Icons.ring_volume_outlined,
          title: 'Answer calls by voice',
          subtitle: 'AERIS says who\'s calling — say "uthao" or "kaat do". Nothing appears on screen, just a glow.',
          trailing: Switch(
            value: enabled,
            onChanged: context.calls == null ? null : (turnOn) => turnOn ? _turnOn(context) : _save(context, false),
          ),
        ),
        if (enabled)
          for (final (icon, title, why, permission) in _requirements)
            PermissionRow(icon: icon, title: title, why: why, permission: permission),
      ]),
      if (enabled) ...[
        const SizedBox(height: S.md),
        HudButton(
          label: 'Rehearse a call',
          icon: Icons.play_arrow_rounded,
          kind: BtnKind.outline,
          // A pretend call from an unknown number: glow + voice, nothing real happens.
          onPressed: () => context.calls?.rehearse(),
        ),
        const SizedBox(height: S.sm),
        const Text(
          'Realme / Oppo phones: also allow Autostart for AERIS (Settings → Apps → AERIS), '
          'or the phone may stop it after a while.',
          style: T.small,
        ),
      ],
    ]);
  }
}
