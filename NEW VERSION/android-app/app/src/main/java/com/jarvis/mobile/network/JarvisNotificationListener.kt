package com.jarvis.mobile.network

import android.service.notification.NotificationListenerService
import android.service.notification.StatusBarNotification
import android.util.Log
import org.json.JSONObject

class JarvisNotificationListener : NotificationListenerService() {
    private val TAG = "JarvisNotifListener"

    companion object {
        private var instance: JarvisNotificationListener? = null
        
        fun triggerSync() {
            instance?.refreshActiveNotifications()
        }
    }

    override fun onListenerConnected() {
        super.onListenerConnected()
        Log.d(TAG, "Notification Listener Connected")
        instance = this
        
        refreshActiveNotifications()
    }

    override fun onDestroy() {
        super.onDestroy()
        if (instance == this) instance = null
    }

    private fun refreshActiveNotifications() {
        try {
            activeNotifications?.forEach { sbn ->
                NotificationRepository.add(sbn)
                // Also send to backend if enabled
                if (SettingsManager.notificationsEnabled) {
                    sendNotification(sbn)
                    NotificationRepository.markAsSent(sbn.key)
                }
            }
        } catch (e: Exception) {
            Log.e(TAG, "Error syncing notifications", e)
        }
    }
    
    override fun onNotificationPosted(sbn: StatusBarNotification) {
        if (shouldIgnore(sbn)) return
        
        Log.d(TAG, "Notification Posted: ${sbn.packageName}")
        NotificationRepository.add(sbn)
        
        if (SettingsManager.notificationsEnabled) {
            sendNotification(sbn)
            NotificationRepository.markAsSent(sbn.key)
        }
    }

    override fun onNotificationRemoved(sbn: StatusBarNotification) {
        if (shouldIgnore(sbn)) return
        
        Log.d(TAG, "Notification Removed: ${sbn.packageName}")
        NotificationRepository.remove(sbn.key)
        
        // Notify backend of removal
        val payload = JSONObject().apply {
            put("key", sbn.key)
        }
        ConnectionManager.send(JSONObject().apply {
            put("type", "notification_removed")
            put("payload", payload)
        }.toString())
    }
    
    private fun shouldIgnore(sbn: StatusBarNotification): Boolean {
        return sbn.packageName == "android" || sbn.packageName == "com.android.systemui"
    }

    private fun sendNotification(sbn: StatusBarNotification) {
        val extras = sbn.notification.extras
        val title = extras.getString(android.app.Notification.EXTRA_TITLE) ?: "No Title"
        val text = extras.getCharSequence(android.app.Notification.EXTRA_TEXT)?.toString() ?: ""
        
        val payload = JSONObject().apply {
            put("key", sbn.key)
            put("app", sbn.packageName)
            put("title", title)
            put("text", text)
            put("timestamp", sbn.postTime)
        }
        
        ConnectionManager.send(JSONObject().apply {
            put("type", "notification")
            put("payload", payload)
        }.toString())
    }
}
