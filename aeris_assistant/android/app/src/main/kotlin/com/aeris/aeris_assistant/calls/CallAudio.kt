package com.aeris.aeris_assistant.calls

import android.app.NotificationManager
import android.content.Context
import android.media.AudioAttributes
import android.media.AudioDeviceInfo
import android.media.AudioManager
import android.media.MediaPlayer
import android.os.Build
import android.os.Handler
import android.os.Looper
import android.util.Log

/**
 * What the phone's audio looks like right now: ringer mode, Do Not Disturb,
 * and whether earbuds / headphones are connected. Dart decides from this
 * whether (and where) AERIS may speak about a call — see
 * lib/calls/call_voice_rules.dart.
 */
object CallAudio {
    private const val TAG = "AerisCalls"

    private val HEADPHONE_TYPES = buildSet {
        add(AudioDeviceInfo.TYPE_BLUETOOTH_A2DP)
        add(AudioDeviceInfo.TYPE_BLUETOOTH_SCO)
        add(AudioDeviceInfo.TYPE_WIRED_HEADSET)
        add(AudioDeviceInfo.TYPE_WIRED_HEADPHONES)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) add(AudioDeviceInfo.TYPE_USB_HEADSET)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) add(AudioDeviceInfo.TYPE_BLE_HEADSET)
    }

    fun isHeadphones(device: AudioDeviceInfo?) = device != null && device.type in HEADPHONE_TYPES

    /**
     * The earbuds / headphones to speak into WHILE THE PHONE RINGS, best first.
     *
     * Bluetooth earbuds have two links: music (A2DP) and call (SCO). When a
     * call rings, the phone opens the call link to send the ringtone to the
     * buds and SUSPENDS the music link — audio sent there "plays" into
     * nothing (seen in the phone's Bluetooth log, 2026-11-17). So the call
     * link comes first; wired headphones have no such split.
     */
    fun earbuds(context: Context): AudioDeviceInfo? {
        val outputs = context.getSystemService(AudioManager::class.java).getDevices(AudioManager.GET_DEVICES_OUTPUTS)
        val preference = listOf(
            AudioDeviceInfo.TYPE_BLUETOOTH_SCO,
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) AudioDeviceInfo.TYPE_BLE_HEADSET else -1,
            AudioDeviceInfo.TYPE_WIRED_HEADPHONES,
            AudioDeviceInfo.TYPE_WIRED_HEADSET,
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) AudioDeviceInfo.TYPE_USB_HEADSET else -1,
            AudioDeviceInfo.TYPE_BLUETOOTH_A2DP,
        )
        return preference.firstNotNullOfOrNull { type -> outputs.firstOrNull { it.type == type } }
    }

    /** "call link (SCO)" / "music link (A2DP)" / … for the log. */
    fun linkName(device: AudioDeviceInfo?): String = when (device?.type) {
        null -> "nothing"
        AudioDeviceInfo.TYPE_BLUETOOTH_SCO -> "call link (SCO)"
        AudioDeviceInfo.TYPE_BLUETOOTH_A2DP -> "music link (A2DP)"
        AudioDeviceInfo.TYPE_BUILTIN_SPEAKER -> "phone speaker"
        AudioDeviceInfo.TYPE_BUILTIN_EARPIECE -> "phone earpiece"
        else -> "device type ${device.type}"
    }

    fun situation(context: Context): Map<String, Any> {
        val audio = context.getSystemService(AudioManager::class.java)
        val ringerMode = when (audio.ringerMode) {
            AudioManager.RINGER_MODE_SILENT -> "silent"
            AudioManager.RINGER_MODE_VIBRATE -> "vibrate"
            else -> "normal"
        }
        val doNotDisturb = context.getSystemService(NotificationManager::class.java).currentInterruptionFilter !=
            NotificationManager.INTERRUPTION_FILTER_ALL
        val buds = earbuds(context)
        return mapOf(
            "ringerMode" to ringerMode,
            "doNotDisturb" to doNotDisturb,
            "earbuds" to (buds != null),
            "earbudsName" to (buds?.productName?.toString() ?: ""),
        )
    }
}

/**
 * Plays one sentence of AERIS's voice while the phone rings (Flutter's audio
 * plugin can't choose the output device, this can).
 *
 * Earbuds-only: the player starts MUTED, checks where Android actually routed
 * it, and only when that is the earbuds rewinds to the start and unmutes — so
 * the voice never leaks out of the phone speaker, and no word is clipped (an
 * earlier version unmuted mid-sentence and cut the first 250 ms off every
 * sentence, which sounded rushed). (During ringing some phones keep
 * the earbuds on the call link and refuse app audio there; then it reports
 * false and AERIS stays quiet.)
 */
object RingingVoicePlayer {
    private const val TAG = "AerisCalls"
    private const val ROUTE_CHECK_MS = 250L
    private val mainHandler = Handler(Looper.getMainLooper())
    private var player: MediaPlayer? = null

    /** Calls [onDone] once: true = played to the end where it was meant to. */
    fun play(context: Context, path: String, earbudsOnly: Boolean, onDone: (Boolean) -> Unit) {
        stop()
        var finished = false
        fun finish(played: Boolean, reason: String) {
            if (finished) return
            finished = true
            Log.i(TAG, "ringing voice: $reason")
            stop()
            onDone(played)
        }

        val buds = if (earbudsOnly) CallAudio.earbuds(context) else null
        if (earbudsOnly && buds == null) return finish(false, "no earbuds connected")

        try {
            val mediaPlayer = MediaPlayer()
            player = mediaPlayer
            val usage = when {
                // aloud: the alarm channel (audible over a ringing phone)
                !earbudsOnly -> AudioAttributes.USAGE_ALARM
                // the earbuds' call link carries voice-call audio
                buds?.type == AudioDeviceInfo.TYPE_BLUETOOTH_SCO -> AudioAttributes.USAGE_VOICE_COMMUNICATION
                // wired / music link: an assistant prompt
                else -> AudioAttributes.USAGE_ASSISTANT
            }
            mediaPlayer.setAudioAttributes(
                AudioAttributes.Builder()
                    .setContentType(AudioAttributes.CONTENT_TYPE_SPEECH)
                    .setUsage(usage)
                    .build(),
            )
            mediaPlayer.setDataSource(path)
            if (buds != null && Build.VERSION.SDK_INT >= Build.VERSION_CODES.P) mediaPlayer.setPreferredDevice(buds)
            mediaPlayer.setOnCompletionListener { finish(true, "played") }
            mediaPlayer.setOnErrorListener { _, what, extra -> finish(false, "player error $what/$extra"); true }
            mediaPlayer.prepare()
            if (earbudsOnly) mediaPlayer.setVolume(0f, 0f) // silent until the route is confirmed
            mediaPlayer.start()
            if (earbudsOnly) {
                mainHandler.postDelayed({
                    if (finished || player !== mediaPlayer) return@postDelayed
                    val routed = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.P) mediaPlayer.routedDevice else null
                    if (CallAudio.isHeadphones(routed)) {
                        mediaPlayer.seekTo(0) // replay from the first word, now audible
                        mediaPlayer.setVolume(1f, 1f)
                        Log.i(TAG, "ringing voice → ${routed?.productName} over the ${CallAudio.linkName(routed)}")
                    } else {
                        finish(false, "Android routed it to the ${CallAudio.linkName(routed)}, not the earbuds — staying quiet")
                    }
                }, ROUTE_CHECK_MS)
            }
        } catch (e: Exception) {
            finish(false, "failed: $e")
        }
    }

    fun stop() {
        val current = player ?: return
        player = null
        try {
            current.stop()
        } catch (_: Exception) {
        }
        current.release()
    }
}
