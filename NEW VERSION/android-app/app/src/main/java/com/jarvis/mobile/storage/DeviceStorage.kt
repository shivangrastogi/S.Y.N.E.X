// Path: d:\New folder (2) - JARVIS\android-app\app\src\main\java\com\jarvis\mobile\storage\DeviceStorage.kt
package com.jarvis.mobile.storage

import android.content.Context
import android.content.SharedPreferences

/**
 * Device Storage - Persistent storage for remembered JARVIS device
 */
class DeviceStorage(context: Context) {
    
    private val prefs: SharedPreferences = context.getSharedPreferences(
        "jarvis_device_prefs", 
        Context.MODE_PRIVATE
    )
    
    companion object {
        private const val KEY_DEVICE_TYPE = "device_type"
        private const val KEY_DEVICE_ADDRESS = "device_address"
        private const val KEY_DEVICE_NAME = "device_name"
        private const val KEY_LAST_CONNECTED = "last_connected"
        
        const val TYPE_BLUETOOTH = "bluetooth"
        const val TYPE_WIFI = "wifi"
    }
    
    data class SavedDevice(
        val type: String,  // "bluetooth" or "wifi"
        val address: String,  // BT MAC or IP address
        val name: String  // Human-readable name
    )
    
    fun saveDevice(type: String, address: String, name: String) {
        prefs.edit().apply {
            putString(KEY_DEVICE_TYPE, type)
            putString(KEY_DEVICE_ADDRESS, address)
            putString(KEY_DEVICE_NAME, name)
            putLong(KEY_LAST_CONNECTED, System.currentTimeMillis())
            apply()
        }
    }
    
    fun getSavedDevice(): SavedDevice? {
        val type = prefs.getString(KEY_DEVICE_TYPE, null) ?: return null
        val address = prefs.getString(KEY_DEVICE_ADDRESS, null) ?: return null
        val name = prefs.getString(KEY_DEVICE_NAME, "JARVIS") ?: "JARVIS"
        
        return SavedDevice(type, address, name)
    }
    
    fun clearSavedDevice() {
        prefs.edit().clear().apply()
    }
    
    fun hasSavedDevice(): Boolean {
        return prefs.contains(KEY_DEVICE_ADDRESS)
    }
    
    fun getLastConnectedTime(): Long {
        return prefs.getLong(KEY_LAST_CONNECTED, 0)
    }
}
