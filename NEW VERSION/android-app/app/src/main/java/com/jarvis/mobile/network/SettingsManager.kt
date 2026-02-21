package com.jarvis.mobile.network

import android.content.Context
import android.content.SharedPreferences

object SettingsManager {
    private const val PREFS_NAME = "JarvisSettings"
    private const val KEY_NOTIFICATIONS_ENABLED = "notifications_enabled"
    private const val KEY_AUTO_CONNECT_ENABLED = "auto_connect_enabled"
    private const val KEY_LAST_TRANSPORT_TYPE = "last_transport_type"
    private const val KEY_ROLE_REQUEST_ATTEMPTED = "role_request_attempted"

    private var prefs: SharedPreferences? = null

    fun initialize(context: Context) {
        if (prefs == null) {
            prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        }
    }

    private fun getPrefs(): SharedPreferences {
        return prefs ?: throw IllegalStateException("SettingsManager not initialized. Call initialize(context) first.")
    }

    var notificationsEnabled: Boolean
        get() = getPrefs().getBoolean(KEY_NOTIFICATIONS_ENABLED, true)
        set(value) = getPrefs().edit().putBoolean(KEY_NOTIFICATIONS_ENABLED, value).apply()

    var autoConnectEnabled: Boolean
        get() = getPrefs().getBoolean(KEY_AUTO_CONNECT_ENABLED, false) // Default to false as requested
        set(value) = getPrefs().edit().putBoolean(KEY_AUTO_CONNECT_ENABLED, value).apply()

    var lastTransportType: String?
        get() = getPrefs().getString(KEY_LAST_TRANSPORT_TYPE, null)
        set(value) = getPrefs().edit().putString(KEY_LAST_TRANSPORT_TYPE, value).apply()

    var roleRequestAttempted: Boolean
        get() = getPrefs().getBoolean(KEY_ROLE_REQUEST_ATTEMPTED, false)
        set(value) = getPrefs().edit().putBoolean(KEY_ROLE_REQUEST_ATTEMPTED, value).apply()
}
