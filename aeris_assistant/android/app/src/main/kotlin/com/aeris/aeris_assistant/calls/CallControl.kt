package com.aeris.aeris_assistant.calls

import android.Manifest
import android.content.Context
import android.content.pm.PackageManager
import android.media.AudioDeviceInfo
import android.media.AudioManager
import android.os.Build
import android.os.Handler
import android.os.Looper
import android.telecom.TelecomManager
import android.telephony.SmsManager
import android.util.Log

/** Answer / reject the ringing call, speakerphone, ringer volume and direct SMS. */
object CallControl {
    private const val TAG = "AerisCalls"

    private fun has(context: Context, permission: String) =
        context.checkSelfPermission(permission) == PackageManager.PERMISSION_GRANTED

    /** Picks up the ringing call. [onSpeaker] switches to the loudspeaker once connected. */
    fun answer(context: Context, onSpeaker: Boolean): Boolean {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O || !has(context, Manifest.permission.ANSWER_PHONE_CALLS)) {
            return false
        }
        return try {
            val telecom = context.getSystemService(TelecomManager::class.java)
            @Suppress("DEPRECATION") // still the only way for a non-dialer app; works on Android 14
            telecom.acceptRingingCall()
            // the call audio route only exists once the call is connected
            if (onSpeaker) Handler(Looper.getMainLooper()).postDelayed({ useSpeaker(context) }, 900)
            true
        } catch (e: Exception) {
            Log.w(TAG, "answer failed: $e")
            false
        }
    }

    /** Declines the ringing call. */
    fun reject(context: Context): Boolean {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.P || !has(context, Manifest.permission.ANSWER_PHONE_CALLS)) {
            return false
        }
        return try {
            @Suppress("DEPRECATION")
            context.getSystemService(TelecomManager::class.java).endCall()
        } catch (e: Exception) {
            Log.w(TAG, "reject failed: $e")
            false
        }
    }

    private fun useSpeaker(context: Context) {
        val audio = context.getSystemService(AudioManager::class.java)
        try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
                audio.availableCommunicationDevices
                    .firstOrNull { it.type == AudioDeviceInfo.TYPE_BUILTIN_SPEAKER }
                    ?.let(audio::setCommunicationDevice)
            } else {
                @Suppress("DEPRECATION")
                audio.isSpeakerphoneOn = true
            }
        } catch (e: Exception) {
            Log.w(TAG, "speaker failed: $e")
        }
    }

    /** Ring volume / ringer mode before [silenceRinger]; -1 = not changed by AERIS. */
    private var savedRingVolume = -1
    private var savedRingerMode = -1
    private val fadeHandler = Handler(Looper.getMainLooper())

    /**
     * Fades the ringtone down to its LOWEST step (never 0) so AERIS can speak
     * and listen over it.
     *
     * Never 0, and never touched unless the phone is in ring mode: on Android
     * ring volume 0 IS vibrate mode, and raising it again switches a vibrating
     * phone to ring mode — AERIS flipped the user's phone between ring and
     * vibrate that way (found on the phone, 2026-11-17). Fully silencing a
     * ringing call is reserved for the system dialer (MODIFY_PHONE_STATE).
     */
    fun silenceRinger(context: Context, fadeMs: Long) {
        val audio = context.getSystemService(AudioManager::class.java)
        if (audio.ringerMode != AudioManager.RINGER_MODE_NORMAL) {
            Log.i(TAG, "ringer: phone is on vibrate/silent — leaving it alone")
            return
        }
        val current = audio.getStreamVolume(AudioManager.STREAM_RING)
        val lowest = maxOf(1, if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.P) audio.getStreamMinVolume(AudioManager.STREAM_RING) else 1)
        if (savedRingVolume < 0) {
            savedRingVolume = current
            savedRingerMode = audio.ringerMode
        }
        Log.i(TAG, "ringer $current → $lowest over $fadeMs ms")
        fadeRingTo(audio, current, lowest, fadeMs) { restoreModeIfChanged(audio) }
    }

    /** Brings the ringtone back to the user's volume and mode, over [fadeMs] (0 = at once). */
    fun restoreRinger(context: Context, fadeMs: Long) {
        if (savedRingVolume < 0) return
        val audio = context.getSystemService(AudioManager::class.java)
        val target = savedRingVolume
        val current = audio.getStreamVolume(AudioManager.STREAM_RING)
        Log.i(TAG, "ringer $current → $target over $fadeMs ms")
        fadeRingTo(audio, current, target, fadeMs) {
            restoreModeIfChanged(audio)
            savedRingVolume = -1
            savedRingerMode = -1
        }
    }

    /** Safety net: if anything moved the phone off the user's ringer mode, put it back. */
    private fun restoreModeIfChanged(audio: AudioManager) {
        if (savedRingerMode < 0 || audio.ringerMode == savedRingerMode) return
        Log.w(TAG, "ringer mode changed to ${audio.ringerMode} — restoring the user's $savedRingerMode")
        try {
            audio.ringerMode = savedRingerMode
        } catch (e: Exception) {
            Log.w(TAG, "can't restore ringer mode: $e")
        }
    }

    /** One volume step at a time, evenly spread over [fadeMs]; [onDone] after the last step. */
    private fun fadeRingTo(audio: AudioManager, from: Int, to: Int, fadeMs: Long, onDone: () -> Unit) {
        fadeHandler.removeCallbacksAndMessages(null) // a new fade replaces the old one
        val steps = kotlin.math.abs(to - from)
        if (steps == 0) {
            onDone()
            return
        }
        val direction = if (to > from) 1 else -1
        val stepDelay = if (fadeMs <= 0) 0L else fadeMs / steps
        for (step in 1..steps) {
            val volume = from + direction * step
            fadeHandler.postDelayed({
                setRingVolume(audio, volume)
                if (step == steps) onDone()
            }, stepDelay * step)
        }
    }

    private fun setRingVolume(audio: AudioManager, volume: Int) {
        try {
            audio.setStreamVolume(AudioManager.STREAM_RING, volume, 0)
        } catch (e: Exception) {
            Log.w(TAG, "ringer volume $volume failed: $e")
        }
    }

    /** Sends an SMS without opening any screen (the user approved it by voice). */
    fun sendText(context: Context, number: String, text: String): Boolean {
        if (!has(context, Manifest.permission.SEND_SMS)) return false
        return try {
            val sms = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
                context.getSystemService(SmsManager::class.java)
            } else {
                @Suppress("DEPRECATION") SmsManager.getDefault()
            }
            sms.sendMultipartTextMessage(number, null, sms.divideMessage(text), null, null)
            true
        } catch (e: Exception) {
            Log.w(TAG, "sms failed: $e")
            false
        }
    }
}
