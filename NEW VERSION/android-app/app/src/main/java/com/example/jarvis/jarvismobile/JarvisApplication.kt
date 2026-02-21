package com.example.jarvis.jarvismobile

import android.app.Application
import com.jarvis.mobile.network.ConnectionManager
import com.jarvis.mobile.network.NotificationRepository
import com.jarvis.mobile.network.SettingsManager

class JarvisApplication : Application() {
    override fun onCreate() {
        super.onCreate()
        
        // Centralized initialization for all components (App UI + Background Services)
        SettingsManager.initialize(this)
        ConnectionManager.initialize(this)
        NotificationRepository.initialize(this)
    }
}
