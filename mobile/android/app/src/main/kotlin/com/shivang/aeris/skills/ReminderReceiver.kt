package com.shivang.aeris.skills

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat
import com.shivang.aeris.AerisApp
import com.shivang.aeris.R

class ReminderReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        val id = intent.getLongExtra("id", 0L).toInt()
        val text = intent.getStringExtra("text") ?: "Reminder"
        val notif = NotificationCompat.Builder(context, AerisApp.CH_REMINDERS)
            .setSmallIcon(R.drawable.ic_launcher_fg)
            .setContentTitle("A.E.R.I.S. reminder")
            .setContentText(text)
            .setStyle(NotificationCompat.BigTextStyle().bigText(text))
            .setPriority(NotificationCompat.PRIORITY_HIGH)
            .setAutoCancel(true)
            .build()
        runCatching { NotificationManagerCompat.from(context).notify(id, notif) }
    }
}
