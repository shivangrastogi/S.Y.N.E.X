package com.aeris.aeris_remote

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.pm.ServiceInfo
import android.os.Build
import android.os.IBinder

// Minimal foreground service so MediaProjection is allowed on Android 14+
// (getMediaProjection throws unless a mediaProjection-type FGS is running).
// It carries no logic — the projection + capture live in MainActivity; this
// just holds the required foreground state during a capture.
class ScreenCaptureService : Service() {
    override fun onBind(intent: Intent?): IBinder? = null

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        val chId = "aeris_screencap"
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val nm = getSystemService(Context.NOTIFICATION_SERVICE)
                    as NotificationManager
            nm.createNotificationChannel(
                NotificationChannel(chId, "Screen sharing",
                    NotificationManager.IMPORTANCE_LOW))
        }
        val notif: Notification = Notification.Builder(this, chId)
            .setContentTitle("AERIS")
            .setContentText("Sharing screen with your laptop")
            .setSmallIcon(android.R.drawable.ic_menu_camera)
            .build()
        try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
                startForeground(9911, notif,
                    ServiceInfo.FOREGROUND_SERVICE_TYPE_MEDIA_PROJECTION)
            } else {
                startForeground(9911, notif)
            }
        } catch (e: Exception) {
            // Never crash the app if the OS refuses the FGS — the WebRTC path
            // will simply fail to capture and Dart falls back to JPEG.
            stopSelf()
        }
        return START_NOT_STICKY
    }
}
