package com.shivang.aeris.skills

import android.app.ActivityManager
import android.content.Context
import android.os.BatteryManager
import android.os.Environment
import android.os.StatFs
import com.shivang.aeris.core.brain.Skill
import com.shivang.aeris.core.brain.SkillReply
import dagger.hilt.android.qualifiers.ApplicationContext
import javax.inject.Inject
import javax.inject.Singleton

/**
 * "system health" / "battery kitna hai" — speaks battery, RAM, storage.
 * Phone equivalents of the desktop's CPU + disk + network reports.
 */
@Singleton
class SystemHealthSkill @Inject constructor(
    @ApplicationContext private val context: Context,
) : Skill {
    override val id = "system.health"
    override val examples = listOf("system health", "battery kitna hai", "phone status")

    private val triggers = listOf(
        "system health", "phone status", "phone health",
        "battery kitna", "battery percent", "battery status",
        "storage kitna", "memory kitna", "ram status",
    )

    override fun match(normalized: String): Float =
        if (triggers.any { normalized.contains(it) }) 0.88f else 0f

    override suspend fun handle(normalized: String, raw: String): SkillReply {
        val bm = context.getSystemService(Context.BATTERY_SERVICE) as BatteryManager
        val battery = bm.getIntProperty(BatteryManager.BATTERY_PROPERTY_CAPACITY)

        val am = context.getSystemService(Context.ACTIVITY_SERVICE) as ActivityManager
        val mem = ActivityManager.MemoryInfo().also(am::getMemoryInfo)
        val ramFreeMb = mem.availMem / (1024 * 1024)
        val ramTotalMb = mem.totalMem / (1024 * 1024)

        val sfs = StatFs(Environment.getDataDirectory().absolutePath)
        val storageFreeGb = sfs.availableBytes / (1024.0 * 1024 * 1024)
        val storageTotalGb = sfs.totalBytes / (1024.0 * 1024 * 1024)

        val spoken = "Battery $battery percent. RAM $ramFreeMb MB free of $ramTotalMb MB. " +
            "Storage ${"%.1f".format(storageFreeGb)} GB free of ${"%.0f".format(storageTotalGb)} GB."

        val display = """
            🔋 Battery: $battery%
            🧠 RAM: $ramFreeMb / $ramTotalMb MB free
            💾 Storage: ${"%.1f".format(storageFreeGb)} / ${"%.0f".format(storageTotalGb)} GB free
        """.trimIndent()

        return SkillReply(spoken, display)
    }
}
