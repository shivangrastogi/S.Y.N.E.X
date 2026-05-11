package com.shivang.aeris.skills

import android.app.AlarmManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import com.shivang.aeris.core.brain.BrainEvent
import com.shivang.aeris.core.brain.Skill
import com.shivang.aeris.core.brain.SkillReply
import dagger.hilt.android.qualifiers.ApplicationContext
import javax.inject.Inject
import javax.inject.Singleton

/** "5 minute ka timer lagao" — fires a notification when time's up. */
@Singleton
class TimerSkill @Inject constructor(
    @ApplicationContext private val context: Context,
) : Skill {
    override val id = "timer.start"
    override val examples = listOf("5 minute ka timer lagao", "set a 30 second timer")

    override fun match(normalized: String): Float {
        val hasTimer = "timer" in normalized
        val hasUnit = Regex("\\b\\d+\\s*(sec|second|min|minute|hour|ghante|ghanta)\\b")
            .containsMatchIn(normalized)
        return if (hasTimer && hasUnit) 0.9f else 0f
    }

    override suspend fun handle(normalized: String, raw: String): SkillReply {
        val m = Regex("(\\d+)\\s*(sec|second|seconds|min|minute|minutes|hour|hours|ghante|ghanta)")
            .find(normalized) ?: return SkillReply("Timer ki duration samajh nahi aayi sir.")
        val n = m.groupValues[1].toInt()
        val unit = m.groupValues[2]
        val sec = when {
            unit.startsWith("sec") -> n
            unit.startsWith("hour") || unit.startsWith("ghan") -> n * 3600
            else -> n * 60
        }
        val whenMillis = System.currentTimeMillis() + sec * 1000L

        val am = context.getSystemService(Context.ALARM_SERVICE) as AlarmManager
        val intent = Intent(context, ReminderReceiver::class.java).apply {
            putExtra("id", whenMillis)
            putExtra("text", "⏲ Timer done — $n $unit")
        }
        val pi = PendingIntent.getBroadcast(
            context, whenMillis.toInt(), intent,
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT,
        )
        am.setExactAndAllowWhileIdle(AlarmManager.RTC_WAKEUP, whenMillis, pi)

        val spoken = "Timer set sir — $n $unit."
        return SkillReply(
            spoken = spoken, display = "⏲ $n $unit",
            event = BrainEvent.TimerStarted(sec),
        )
    }
}
