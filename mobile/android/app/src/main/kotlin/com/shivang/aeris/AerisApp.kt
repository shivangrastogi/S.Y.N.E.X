package com.shivang.aeris

import android.app.Application
import android.app.NotificationChannel
import android.app.NotificationManager
import android.os.Build
import androidx.hilt.work.HiltWorkerFactory
import androidx.work.Configuration
import dagger.hilt.android.HiltAndroidApp
import timber.log.Timber
import javax.inject.Inject

@HiltAndroidApp
class AerisApp : Application(), Configuration.Provider {

    @Inject lateinit var workerFactory: HiltWorkerFactory

    override fun onCreate() {
        super.onCreate()
        if (BuildConfig.DEBUG) Timber.plant(Timber.DebugTree())
        registerNotificationChannels()
    }

    override val workManagerConfiguration: Configuration
        get() = Configuration.Builder()
            .setWorkerFactory(workerFactory)
            .build()

    private fun registerNotificationChannels() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return
        val nm = getSystemService(NotificationManager::class.java)
        listOf(
            NotificationChannel(CH_REMINDERS, "Reminders", NotificationManager.IMPORTANCE_HIGH),
            NotificationChannel(CH_TIMERS, "Timers", NotificationManager.IMPORTANCE_HIGH),
            NotificationChannel(CH_VOICE, "Voice service", NotificationManager.IMPORTANCE_LOW),
        ).forEach(nm::createNotificationChannel)
    }

    companion object {
        const val CH_REMINDERS = "aeris.reminders"
        const val CH_TIMERS = "aeris.timers"
        const val CH_VOICE = "aeris.voice"
    }
}
