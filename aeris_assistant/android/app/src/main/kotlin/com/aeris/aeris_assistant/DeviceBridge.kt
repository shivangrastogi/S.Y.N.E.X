package com.aeris.aeris_assistant

import android.app.AlarmManager
import android.app.NotificationManager
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.media.AudioManager
import android.os.Handler
import android.os.Looper
import android.provider.Settings
import android.view.KeyEvent
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodChannel
import kotlin.math.roundToInt

/**
 * Phone controls Dart can't reach through plugins. Dart side: lib/brain/phone.dart
 * (AndroidPhone), method channel `aeris/device`.
 *
 *   volume(action, level?)  media volume up/down/mute/unmute/max/set → percent afterwards
 *   media(action)           play/pause/toggle/next/previous as a media key → for play: is music playing now?
 *   ringer(mode)            silent/vibrate/normal → false when Do Not Disturb access is missing
 *   openDndAccess()         the settings page that grants it
 *   nextAlarm()             epoch ms of the next alarm any app set, or null
 *   apps()                  launchable apps: [{label, package}]
 */
object DeviceBridge {
    private val mainHandler = Handler(Looper.getMainLooper())

    fun attach(engine: FlutterEngine, appContext: Context) {
        MethodChannel(engine.dartExecutor.binaryMessenger, "aeris/device").setMethodCallHandler { call, result ->
            try {
                when (call.method) {
                    "volume" -> result.success(volume(appContext, call.argument<String>("action") ?: "up", call.argument<Int>("level")))
                    "media" -> media(appContext, call.argument<String>("action") ?: "toggle") { result.success(it) }
                    "ringer" -> result.success(ringer(appContext, call.argument<String>("mode") ?: "normal"))
                    "openDndAccess" -> {
                        appContext.startActivity(
                            Intent(Settings.ACTION_NOTIFICATION_POLICY_ACCESS_SETTINGS).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK),
                        )
                        result.success(null)
                    }
                    "nextAlarm" -> {
                        val alarms = appContext.getSystemService(Context.ALARM_SERVICE) as AlarmManager
                        result.success(alarms.nextAlarmClock?.triggerTime)
                    }
                    "apps" -> result.success(launchableApps(appContext))
                    else -> result.notImplemented()
                }
            } catch (e: Exception) {
                result.error("device", e.message, null)
            }
        }
    }

    private fun audio(context: Context) = context.getSystemService(Context.AUDIO_SERVICE) as AudioManager

    /** Changes the media volume (with the system slider shown) and returns it in percent. */
    private fun volume(context: Context, action: String, level: Int?): Int {
        val audio = audio(context)
        val stream = AudioManager.STREAM_MUSIC
        val max = audio.getStreamMaxVolume(stream)
        val show = AudioManager.FLAG_SHOW_UI
        when (action) {
            "up" -> repeat(2) { audio.adjustStreamVolume(stream, AudioManager.ADJUST_RAISE, show) }
            "down" -> repeat(2) { audio.adjustStreamVolume(stream, AudioManager.ADJUST_LOWER, show) }
            "mute" -> audio.adjustStreamVolume(stream, AudioManager.ADJUST_MUTE, show)
            "unmute" -> audio.adjustStreamVolume(stream, AudioManager.ADJUST_UNMUTE, show)
            "max" -> audio.setStreamVolume(stream, max, show)
            "set" -> audio.setStreamVolume(stream, ((level ?: 50).coerceIn(0, 100) * max / 100.0).roundToInt(), show)
        }
        if (action != "mute" && audio.isStreamMute(stream)) audio.adjustStreamVolume(stream, AudioManager.ADJUST_UNMUTE, 0)
        return if (audio.isStreamMute(stream)) 0 else (audio.getStreamVolume(stream) * 100.0 / max).roundToInt()
    }

    /**
     * Sends a media key to whatever is playing. For "play" it waits a moment
     * and reports whether music actually started — false means nothing was
     * paused, so Dart starts a music app instead.
     */
    private fun media(context: Context, action: String, done: (Boolean) -> Unit) {
        val code = when (action) {
            "play" -> KeyEvent.KEYCODE_MEDIA_PLAY
            "pause" -> KeyEvent.KEYCODE_MEDIA_PAUSE
            "next" -> KeyEvent.KEYCODE_MEDIA_NEXT
            "previous" -> KeyEvent.KEYCODE_MEDIA_PREVIOUS
            else -> KeyEvent.KEYCODE_MEDIA_PLAY_PAUSE
        }
        val audio = audio(context)
        audio.dispatchMediaKeyEvent(KeyEvent(KeyEvent.ACTION_DOWN, code))
        audio.dispatchMediaKeyEvent(KeyEvent(KeyEvent.ACTION_UP, code))
        if (action == "play") {
            mainHandler.postDelayed({ done(audio.isMusicActive) }, 700)
        } else {
            done(true)
        }
    }

    /** Silent needs Do Not Disturb access on Android 7+; without it this returns false. */
    private fun ringer(context: Context, mode: String): Boolean {
        val notifications = context.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        val audio = audio(context)
        val target = when (mode) {
            "silent" -> AudioManager.RINGER_MODE_SILENT
            "vibrate" -> AudioManager.RINGER_MODE_VIBRATE
            else -> AudioManager.RINGER_MODE_NORMAL
        }
        val leavingSilent = audio.ringerMode == AudioManager.RINGER_MODE_SILENT
        if ((target == AudioManager.RINGER_MODE_SILENT || leavingSilent) && !notifications.isNotificationPolicyAccessGranted) {
            return false
        }
        return try {
            audio.ringerMode = target
            true
        } catch (e: SecurityException) {
            false
        }
    }

    private fun launchableApps(context: Context): List<Map<String, String>> {
        val pm = context.packageManager
        val launcher = Intent(Intent.ACTION_MAIN).addCategory(Intent.CATEGORY_LAUNCHER)
        @Suppress("DEPRECATION")
        val activities = pm.queryIntentActivities(launcher, PackageManager.MATCH_ALL)
        return activities
            .map { mapOf("label" to it.loadLabel(pm).toString(), "package" to it.activityInfo.packageName) }
            .distinctBy { it["package"] }
    }
}
