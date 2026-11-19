import 'package:flutter/material.dart';
import 'package:permission_handler/permission_handler.dart';

import '../../ui/kit/controls.dart';
import '../../ui/tokens.dart';

/// A settings row for one Android permission: "Allowed", or an Allow button.
///
/// Keeps its own status and re-checks when the user comes back from the
/// system settings screen, so the parent doesn't track permissions itself.
class PermissionRow extends StatefulWidget {
  const PermissionRow({
    super.key,
    required this.icon,
    required this.title,
    required this.why,
    required this.permission,
  });

  final IconData icon;
  final String title;

  /// One line: what AERIS needs it for.
  final String why;
  final Permission permission;

  @override
  State<PermissionRow> createState() => _PermissionRowState();
}

class _PermissionRowState extends State<PermissionRow> with WidgetsBindingObserver {
  PermissionStatus? _status;

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

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed) _refresh(); // back from system settings
  }

  Future<void> _refresh() async {
    final status = await widget.permission.status;
    if (mounted) setState(() => _status = status);
  }

  Future<void> _request() async {
    final result = await widget.permission.request();
    if (result.isPermanentlyDenied) await openAppSettings();
    await _refresh();
  }

  @override
  Widget build(BuildContext context) {
    final granted = _status?.isGranted ?? false;
    return SettingRow(
      icon: widget.icon,
      title: widget.title,
      subtitle: widget.why,
      trailing: granted
          ? Text('Allowed', style: T.small.copyWith(color: C.mint))
          : TextButton(
              onPressed: _request,
              child: Text('Allow', style: T.body.copyWith(color: C.cyan, fontSize: 14)),
            ),
    );
  }
}
