package com.shivang.aeris.core.brain

/**
 * One A.E.R.I.S. capability — same shape as the desktop `@skill` decorator.
 * `match` returns a confidence score in [0,1]; the brain picks the highest.
 */
interface Skill {
    val id: String
    val examples: List<String>

    fun match(normalized: String): Float
    suspend fun handle(normalized: String, raw: String): SkillReply
}

data class SkillReply(
    val spoken: String,
    val display: String = spoken,
    /** Optional structured payload for UI tabs to react to (e.g. expense added). */
    val event: BrainEvent? = null,
)

sealed interface BrainEvent {
    data class ExpenseAdded(val amount: Int, val category: String) : BrainEvent
    data class TaskAdded(val title: String) : BrainEvent
    data class ReminderSet(val text: String, val whenMillis: Long) : BrainEvent
    data class TimerStarted(val seconds: Int) : BrainEvent
    data class WebSearchDone(val query: String, val cached: Boolean) : BrainEvent
    data object VisionTriggered : BrainEvent
}
