// Main-isolate side of the wake-word service: start/stop, the sleep state,
// and the permission checklist (mic, notifications, battery exemption,
// overlay, ColorOS autostart) that keeps the service alive on Realme.
import 'package:flutter_foreground_task/flutter_foreground_task.dart';
import 'package:permission_handler/permission_handler.dart';
import 'wake_service.dart';

class WakeController {
  /// Call once in main() before runApp.
  static void initPort() => FlutterForegroundTask.initCommunicationPort();

  static void _init() {
    FlutterForegroundTask.init(
      androidNotificationOptions: AndroidNotificationOptions(
        channelId: 'aeris_wake',
        channelName: 'AERIS wake word',
        channelDescription: 'Hamesha "Aeris" sunta rehta hai',
        channelImportance: NotificationChannelImportance.LOW,
        priority: NotificationPriority.LOW,
        onlyAlertOnce: true,
      ),
      iosNotificationOptions: const IOSNotificationOptions(),
      foregroundTaskOptions: ForegroundTaskOptions(
        // Watchdog tick every 30s (see onRepeatEvent); no heavy work.
        eventAction: ForegroundTaskEventAction.repeat(30000),
        autoRunOnBoot: true, // restart after reboot
        allowWakeLock: true, // keep the CPU up with the screen off
        allowWifiLock: false,
      ),
    );
  }

  static Future<bool> get isRunning => FlutterForegroundTask.isRunningService;

  static Future<bool> get enabled async =>
      await FlutterForegroundTask.getData<bool>(key: WakeKeys.enabled) ??
      false;

  /// Start (or restart) the always-listening service.
  static Future<bool> start() async {
    if (!await Permission.microphone.request().isGranted) return false;
    _init();
    await FlutterForegroundTask.saveData(key: WakeKeys.enabled, value: true);
    await FlutterForegroundTask.saveData(key: WakeKeys.asleep, value: false);
    if (await FlutterForegroundTask.isRunningService) {
      await FlutterForegroundTask.restartService();
    } else {
      await FlutterForegroundTask.startService(
        serviceId: 4321,
        notificationTitle: 'AERIS shuru ho raha hai…',
        notificationText: '',
        notificationButtons: [
          const NotificationButton(id: WakeButtons.sleepToggle, text: 'Sleep'),
        ],
        callback: startWakeService,
      );
    }
    return true;
  }

  static Future<void> stop() async {
    await FlutterForegroundTask.saveData(key: WakeKeys.enabled, value: false);
    await FlutterForegroundTask.stopService();
  }

  /// Auto-start on app launch if the user left it enabled.
  static Future<void> ensureStarted() async {
    if (await enabled && !await FlutterForegroundTask.isRunningService) {
      await start();
    }
  }

  // ── A11: wake sensitivity ('low' | 'balanced' | 'high') ──────────
  static Future<String> get sensitivity async =>
      await FlutterForegroundTask.getData<String>(
          key: WakeKeys.sensitivity) ??
      'balanced';

  static Future<void> setSensitivity(String v) async {
    await FlutterForegroundTask.saveData(
        key: WakeKeys.sensitivity, value: v);
    // The spotter reads it at construction — restart to apply live.
    if (await FlutterForegroundTask.isRunningService) {
      await FlutterForegroundTask.restartService();
    }
  }

  // ── Wake events from the service ──────────────────────────────────
  static void addListener(void Function(Object) cb) =>
      FlutterForegroundTask.addTaskDataCallback(cb);
  static void removeListener(void Function(Object) cb) =>
      FlutterForegroundTask.removeTaskDataCallback(cb);

  /// True once if the app was just launched by the hotword (cold start —
  /// the wake event over the port is lost when no main isolate exists yet).
  static Future<bool> consumePendingWake() async {
    final ts =
        await FlutterForegroundTask.getData<int>(key: WakeKeys.pendingWake);
    if (ts == null) return false;
    await FlutterForegroundTask.removeData(key: WakeKeys.pendingWake);
    // 30s (was 12s): a cold start from a fully-killed app on ColorOS can take
    // well over 12s to reach here, which silently dropped the wake → no
    // overlay when woken from the home screen.
    return DateTime.now().millisecondsSinceEpoch - ts < 30000;
  }

  // ── Conversation-mode mic handoff ─────────────────────────────────
  static Future<void> _cmd(String c) async {
    if (await FlutterForegroundTask.isRunningService) {
      FlutterForegroundTask.sendDataToTask({'cmd': c});
    }
  }

  static Future<void> pauseMic() => _cmd(WakeCommands.pauseMic);
  static Future<void> resumeMic() => _cmd(WakeCommands.resumeMic);
  static Future<void> sleep() => _cmd(WakeCommands.sleep);
  static Future<void> wakeUp() => _cmd(WakeCommands.wakeUp);

  // ── Keep-alive permissions (the ColorOS survival kit) ─────────────
  static Future<bool> get batteryExempt =>
      FlutterForegroundTask.isIgnoringBatteryOptimizations;
  static Future<void> requestBatteryExempt() =>
      FlutterForegroundTask.requestIgnoreBatteryOptimization();

  static Future<bool> get canOverlay => FlutterForegroundTask.canDrawOverlays;
  static Future<void> requestOverlay() =>
      FlutterForegroundTask.openSystemAlertWindowSettings();

  static Future<bool> get notificationsOk async =>
      (await FlutterForegroundTask.checkNotificationPermission()) ==
      NotificationPermission.granted;
  static Future<void> requestNotifications() =>
      FlutterForegroundTask.requestNotificationPermission();
}
