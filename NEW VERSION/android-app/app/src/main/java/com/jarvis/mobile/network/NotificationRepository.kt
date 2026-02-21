package com.jarvis.mobile.network

import android.app.Notification
import android.content.Context
import android.service.notification.StatusBarNotification
import android.util.Log
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.io.FileWriter
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow

object NotificationRepository {
    private const val TAG = "NotificationRepository"
    // In-memory cache of valid notifications
    private val activeNotifications = mutableMapOf<String, JSONObject>()
    private var storageFile: File? = null
    
    // UI Observation
    private val _notifications = kotlinx.coroutines.flow.MutableStateFlow<List<JSONObject>>(emptyList())
    val notifications = _notifications.asStateFlow()

    fun initialize(context: Context) {
        storageFile = File(context.filesDir, "notifications.json")
        loadFromFile()
    }

    fun add(sbn: StatusBarNotification) {
        if (!sbn.isClearable) return 

        val extras = sbn.notification.extras
        val title = extras.getString(Notification.EXTRA_TITLE) ?: "No Title"
        val text = extras.getCharSequence(Notification.EXTRA_TEXT)?.toString() ?: ""
        
        val jsonObj = JSONObject().apply {
            put("key", sbn.key)
            put("app", sbn.packageName)
            put("title", title)
            put("text", text)
            put("timestamp", sbn.postTime)
            put("sent", false) // Track if synced to backend
        }
        
        activeNotifications[sbn.key] = jsonObj
        saveToFile()
        updateFlow()
    }
    
    fun markAsSent(key: String) {
        activeNotifications[key]?.put("sent", true)
        saveToFile()
        updateFlow()
    }

    fun remove(key: String) {
        if (activeNotifications.containsKey(key)) {
            activeNotifications.remove(key)
            Log.d(TAG, "Removed notification: $key")
            saveToFile()
            updateFlow()
        }
    }
    
    fun getAll(): List<JSONObject> {
        return activeNotifications.values.toList()
    }
    
    fun getUnsent(): List<JSONObject> {
        return activeNotifications.values.filter { !it.optBoolean("sent", false) }
    }
    
    fun clear() {
        activeNotifications.clear()
        saveToFile()
        updateFlow()
    }

    private fun updateFlow() {
        _notifications.value = activeNotifications.values.toList()
    }

    private fun saveToFile() {
        val file = storageFile ?: return
        try {
            val arr = JSONArray()
            activeNotifications.values.forEach { arr.put(it) }
            FileWriter(file).use { it.write(arr.toString()) }
        } catch (e: Exception) {
            Log.e(TAG, "Failed to save notifications", e)
        }
    }

    private fun loadFromFile() {
        val file = storageFile ?: return
        if (!file.exists()) return
        try {
            val content = file.readText()
            val arr = JSONArray(content)
            activeNotifications.clear()
            for (i in 0 until arr.length()) {
                val obj = arr.getJSONObject(i)
                val key = obj.getString("key")
                activeNotifications[key] = obj
            }
            updateFlow()
        } catch (e: Exception) {
            Log.e(TAG, "Failed to load notifications", e)
        }
    }
}
