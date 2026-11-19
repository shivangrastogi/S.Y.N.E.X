package com.aeris.aeris_assistant.calls

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.content.pm.ServiceInfo
import android.os.Build
import android.os.Handler
import android.os.IBinder
import android.os.Looper
import android.telephony.TelephonyManager
import android.util.Log
import com.aeris.aeris_assistant.AerisEngine
import com.aeris.aeris_assistant.MainActivity
import com.aeris.aeris_assistant.R

/**
 * Foreground service that watches for incoming calls and tells Dart about
 * them ("ringing" with the number, "answered", "ended").
 *
 * Why a foreground service: Android only lets an app use the microphone in the
 * background from one, and it keeps the process (and the Dart engine with the
 * voice models) alive while the app's screen is closed. Its notification is
 * the user-visible sign that AERIS is ready.
 *
 * It must be started while the app is on screen (Android 14 forbids starting a
 * microphone service from the background) — Dart starts it from the app.
 */
class CallWatchService : Service() {

    companion object {
        private const val TAG = "AerisCalls"
        private const val CHANNEL_ID = "aeris_calls"
        private const val NOTIFICATION_ID = 7301

        /** How long to wait for the second PHONE_STATE broadcast that carries the number. */
        private const val NUMBER_WAIT_MS = 700L

        @Volatile
        var isRunning = false
            private set

        fun start(context: Context) {
            val intent = Intent(context, CallWatchService::class.java)
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) context.startForegroundService(intent)
            else context.startService(intent)
        }

        fun stop(context: Context) {
            context.stopService(Intent(context, CallWatchService::class.java))
        }
    }

    private val mainHandler = Handler(Looper.getMainLooper())
    private var lastState = TelephonyManager.EXTRA_STATE_IDLE
    private var ringingAnnounced = false
    private var pendingRingAnnouncement: Runnable? = null

    /**
     * Android sends PHONE_STATE twice per change: once without the number and,
     * if READ_CALL_LOG is granted, once with it.
     */
    private val phoneStateReceiver = object : BroadcastReceiver() {
        override fun onReceive(context: Context, intent: Intent) {
            val state = intent.getStringExtra(TelephonyManager.EXTRA_STATE) ?: return
            @Suppress("DEPRECATION")
            val number = intent.getStringExtra(TelephonyManager.EXTRA_INCOMING_NUMBER)
            onPhoneState(state, number)
        }
    }

    override fun onCreate() {
        super.onCreate()
        AerisEngine.obtain(this) // make sure Dart is running to handle the call
        if (!startAsForeground()) {
            stopSelf()
            return
        }
        isRunning = true
        val filter = IntentFilter(TelephonyManager.ACTION_PHONE_STATE_CHANGED)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            registerReceiver(phoneStateReceiver, filter, Context.RECEIVER_EXPORTED)
        } else {
            registerReceiver(phoneStateReceiver, filter)
        }
        Log.i(TAG, "watching for calls")
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int = START_STICKY

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onDestroy() {
        if (isRunning) unregisterReceiver(phoneStateReceiver)
        isRunning = false
        pendingRingAnnouncement?.let(mainHandler::removeCallbacks)
        CallControl.restoreRinger(this, 0)
        EdgeGlowOverlay.hideNow(this)
        super.onDestroy()
    }

    private fun onPhoneState(state: String, number: String?) {
        when (state) {
            TelephonyManager.EXTRA_STATE_RINGING -> {
                if (ringingAnnounced) return
                if (!number.isNullOrBlank()) {
                    announceRinging(number)
                } else if (pendingRingAnnouncement == null) {
                    // wait briefly for the broadcast that carries the number
                    val announce = Runnable { announceRinging(null) }
                    pendingRingAnnouncement = announce
                    mainHandler.postDelayed(announce, NUMBER_WAIT_MS)
                }
            }
            TelephonyManager.EXTRA_STATE_OFFHOOK -> {
                cancelPendingAnnouncement()
                // OFFHOOK straight from IDLE is an outgoing call — not ours.
                if (lastState == TelephonyManager.EXTRA_STATE_RINGING) CallBridge.emit("answered")
            }
            TelephonyManager.EXTRA_STATE_IDLE -> {
                cancelPendingAnnouncement()
                if (lastState != TelephonyManager.EXTRA_STATE_IDLE) CallBridge.emit("ended")
                ringingAnnounced = false
            }
        }
        lastState = state
    }

    private fun announceRinging(number: String?) {
        cancelPendingAnnouncement()
        if (ringingAnnounced) return
        ringingAnnounced = true
        val callerName = number?.let { CallerLookup.nameFor(this, it) } ?: ""
        CallBridge.emit("ringing", mapOf("number" to (number ?: ""), "name" to callerName))
    }

    private fun cancelPendingAnnouncement() {
        pendingRingAnnouncement?.let(mainHandler::removeCallbacks)
        pendingRingAnnouncement = null
    }

    /** Returns false when Android refuses (e.g. restarted from the background on Android 14). */
    private fun startAsForeground(): Boolean = try {
        val notification = buildNotification()
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
            startForeground(NOTIFICATION_ID, notification, ServiceInfo.FOREGROUND_SERVICE_TYPE_MICROPHONE)
        } else {
            startForeground(NOTIFICATION_ID, notification)
        }
        true
    } catch (e: Exception) {
        Log.w(TAG, "can't run in the foreground now: $e")
        false
    }

    private fun buildNotification(): Notification {
        val manager = getSystemService(NotificationManager::class.java)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            manager.createNotificationChannel(
                NotificationChannel(CHANNEL_ID, "Calls by voice", NotificationManager.IMPORTANCE_MIN).apply {
                    description = "Shown while AERIS is ready to answer calls by voice"
                    setShowBadge(false)
                },
            )
        }
        val openApp = PendingIntent.getActivity(
            this, 0, Intent(this, MainActivity::class.java),
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT,
        )
        val builder = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) Notification.Builder(this, CHANNEL_ID)
        else @Suppress("DEPRECATION") Notification.Builder(this)
        return builder
            .setSmallIcon(R.mipmap.ic_launcher)
            .setContentTitle("AERIS is ready")
            .setContentText("Incoming calls: say \"uthao\" or \"kaat do\"")
            .setContentIntent(openApp)
            .setOngoing(true)
            .build()
    }
}
