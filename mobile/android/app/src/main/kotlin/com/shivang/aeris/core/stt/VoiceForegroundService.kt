package com.shivang.aeris.core.stt

import android.app.Notification
import android.app.PendingIntent
import android.app.Service
import android.content.Intent
import android.content.pm.ServiceInfo
import android.os.Build
import android.os.IBinder
import androidx.core.app.NotificationCompat
import com.shivang.aeris.AerisApp
import com.shivang.aeris.MainActivity
import com.shivang.aeris.R

/**
 * Hosts the mic when the user wants always-on listening from the lockscreen.
 * Stays minimal — actual recognition happens in [SttEngine]; this service just
 * keeps the process alive with the required `microphone` foreground type.
 */
class VoiceForegroundService : Service() {

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        startInForeground()
        return START_STICKY
    }

    private fun startInForeground() {
        val tap = PendingIntent.getActivity(
            this, 0, Intent(this, MainActivity::class.java),
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT,
        )
        val notif: Notification = NotificationCompat.Builder(this, AerisApp.CH_VOICE)
            .setContentTitle("A.E.R.I.S. listening")
            .setContentText("Tap to open")
            .setSmallIcon(R.drawable.ic_launcher_fg)
            .setOngoing(true)
            .setContentIntent(tap)
            .build()
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            startForeground(NOTIF_ID, notif, ServiceInfo.FOREGROUND_SERVICE_TYPE_MICROPHONE)
        } else {
            startForeground(NOTIF_ID, notif)
        }
    }

    private companion object { const val NOTIF_ID = 7011 }
}
