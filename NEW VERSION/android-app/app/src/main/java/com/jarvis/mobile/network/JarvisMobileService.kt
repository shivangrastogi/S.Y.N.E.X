package com.jarvis.mobile.network

import android.app.*
import android.content.Context
import android.content.Intent
import android.os.Binder
import android.os.Build
import android.os.IBinder
import android.os.PowerManager
import android.util.Log
import androidx.core.app.NotificationCompat
import com.example.jarvis.jarvismobile.MainActivity

class JarvisMobileService : Service() {
    private val TAG = "JarvisMobileService"
    private val NOTIFICATION_ID = 1
    private val CHANNEL_ID = "jarvis_service_channel"
    
    private var wakeLock: PowerManager.WakeLock? = null
    private val binder = LocalBinder()

    inner class LocalBinder : Binder() {
        fun getService(): JarvisMobileService = this@JarvisMobileService
    }

    override fun onBind(intent: Intent?): IBinder = binder

    override fun onCreate() {
        super.onCreate()
        createNotificationChannel()
        startForeground(NOTIFICATION_ID, createNotification("Initialized"))
        
        // Keep CPU alive
        val powerManager = getSystemService(Context.POWER_SERVICE) as PowerManager
        wakeLock = powerManager.newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "Jarvis::ConnectionLock")
        wakeLock?.acquire(10*60*1000L /*10 mins*/)
        
        Log.d(TAG, "JarvisMobileService created")
        
        // Initialize Manager
        ConnectionManager.setService(this)
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        val action = intent?.action
        if (action == "STOP_SERVICE") {
            stopForeground(true)
            stopSelf()
            return START_NOT_STICKY
        }
        
        // Default to Wi-Fi if nothing is active?
        // Let's leave it to user/main activity to enable mode.
        // Or if auto-connect is stored in prefs, we could Trigger it here.
        // For now, adhere to requirement "User must be able to Enable Wi-Fi discovery"
        // But also "Reconnect automatically when desired"
        
        return START_STICKY
    }

    fun updateStatus(status: String) {
        val notificationManager = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        notificationManager.notify(NOTIFICATION_ID, createNotification(status))
    }

    private fun createNotification(content: String): Notification {
        val notificationIntent = Intent(this, MainActivity::class.java)
        // Flag Immutable for Android 12+
        val pendingIntent = PendingIntent.getActivity(
            this, 0, notificationIntent,
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT
        )

        return NotificationCompat.Builder(this, CHANNEL_ID)
            .setContentTitle("JARVIS Mobile")
            .setContentText(content)
            .setSmallIcon(android.R.drawable.ic_menu_info_details) // Using system icon
            .setContentIntent(pendingIntent)
            .setOngoing(true)
            .setCategory(Notification.CATEGORY_SERVICE)
            .setPriority(NotificationCompat.PRIORITY_LOW)
            .build()
    }

    private fun createNotificationChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val serviceChannel = NotificationChannel(
                CHANNEL_ID,
                "JARVIS Background Service",
                NotificationManager.IMPORTANCE_LOW
            )
            val manager = getSystemService(NotificationManager::class.java)
            manager.createNotificationChannel(serviceChannel)
        }
    }

    override fun onDestroy() {
        super.onDestroy()
        try {
            wakeLock?.release()
        } catch (e: Exception) {}
        ConnectionManager.disconnect()
        Log.d(TAG, "JarvisMobileService destroyed")
    }
}
