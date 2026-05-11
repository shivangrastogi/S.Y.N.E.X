package com.shivang.aeris.skills

import android.app.AlarmManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import com.shivang.aeris.core.brain.BrainEvent
import com.shivang.aeris.core.brain.Skill
import com.shivang.aeris.core.brain.SkillReply
import com.shivang.aeris.data.repo.WorkbookRepo
import dagger.hilt.android.qualifiers.ApplicationContext
import javax.inject.Inject
import javax.inject.Singleton

/** "10 minute mein chai yaad dilana" / "remind me in 30 minutes drink water" */
@Singleton
class ReminderSkill @Inject constructor(
    @ApplicationContext private val context: Context,
    private val repo: WorkbookRepo,
) : Skill {
    override val id = "reminder.set"
    override val examples = listOf(
        "10 minute mein chai yaad dilana",
        "remind me in 30 minutes to drink water",
    )

    private val triggers = listOf("yaad dila", "remind", "yaad dilana", "yaad dilao")

    override fun match(normalized: String): Float {
        val hasTrigger = triggers.any { normalized.contains(it) }
        val hasMinutes = Regex("\\b\\d+\\s*(min|minute|minutes|ghante|ghanta|hour|hours)\\b")
            .containsMatchIn(normalized)
        return if (hasTrigger && hasMinutes) 0.88f else 0f
    }

    override suspend fun handle(normalized: String, raw: String): SkillReply {
        val match = Regex("(\\d+)\\s*(min|minute|minutes|ghante|ghanta|hour|hours)").find(normalized)
            ?: return SkillReply("Time samajh nahi aaya sir.")
        val n = match.groupValues[1].toInt()
        val unit = match.groupValues[2]
        val seconds = if (unit.startsWith("ghan") || unit.startsWith("hour")) n * 3600 else n * 60
        val triggerAt = System.currentTimeMillis() + seconds * 1000L

        val text = raw.substringAfterLast("dila", missingDelimiterValue = raw)
            .ifBlank { raw }.trim()

        val id = repo.addReminder(text, triggerAt)
        scheduleAlarm(id, text, triggerAt)

        val spoken = if (seconds < 3600) "$n minute mein yaad dila dunga sir."
        else "${seconds / 3600} ghante baad yaad dila dunga sir."
        return SkillReply(
            spoken = spoken,
            display = "⏰ $text → in $n $unit",
            event = BrainEvent.ReminderSet(text, triggerAt),
        )
    }

    private fun scheduleAlarm(id: Long, text: String, whenMillis: Long) {
        val am = context.getSystemService(Context.ALARM_SERVICE) as AlarmManager
        val intent = Intent(context, ReminderReceiver::class.java).apply {
            putExtra("id", id)
            putExtra("text", text)
        }
        val pi = PendingIntent.getBroadcast(
            context, id.toInt(), intent,
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT,
        )
        if (android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.S &&
            !am.canScheduleExactAlarms()) {
            am.set(AlarmManager.RTC_WAKEUP, whenMillis, pi)
        } else {
            am.setExactAndAllowWhileIdle(AlarmManager.RTC_WAKEUP, whenMillis, pi)
        }
    }
}
