import 'package:flutter/widgets.dart';

import '../calls/call_assistant.dart';
import '../core/store.dart';
import '../voice/session.dart';

/// Hands the long-lived objects down the tree. Widgets listen with
/// ListenableBuilder where they need rebuilds.
class AppScope extends InheritedWidget {
  const AppScope({super.key, required this.store, required this.session, this.calls, required super.child});
  final Store store;
  final VoiceSession session;

  /// Incoming calls by voice. Null in tests and screenshots.
  final CallAssistant? calls;

  static AppScope of(BuildContext context) =>
      context.dependOnInheritedWidgetOfExactType<AppScope>()!;

  @override
  bool updateShouldNotify(AppScope old) => old.store != store || old.session != session || old.calls != calls;
}

extension ScopeX on BuildContext {
  Store get store => AppScope.of(this).store;
  VoiceSession get session => AppScope.of(this).session;
  CallAssistant? get calls => AppScope.of(this).calls;
}
