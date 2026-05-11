package com.shivang.aeris.skills

import com.shivang.aeris.core.brain.BrainEvent
import com.shivang.aeris.core.brain.Skill
import com.shivang.aeris.core.brain.SkillReply
import com.shivang.aeris.data.repo.WorkbookRepo
import javax.inject.Inject
import javax.inject.Singleton

/** "add task finish report by friday urgent" */
@Singleton
class TaskSkill @Inject constructor(
    private val repo: WorkbookRepo,
) : Skill {
    override val id = "task.add"
    override val examples = listOf("add task finish report friday urgent")

    private val triggerRe = Regex(
        "^(add task|task add|note|todo|naya task|task likho|kaam add)\\b",
        RegexOption.IGNORE_CASE,
    )

    override fun match(normalized: String): Float =
        if (triggerRe.containsMatchIn(normalized)) 0.85f else 0f

    override suspend fun handle(normalized: String, raw: String): SkillReply {
        val priority = when {
            "urgent" in normalized || "important" in normalized -> "urgent"
            "later" in normalized || "kabhi bhi" in normalized -> "low"
            else -> "normal"
        }
        val title = raw.replace(triggerRe, "").trim().ifBlank { raw.trim() }
        repo.addTask(title, priority)
        val spoken = "Note kar liya sir: \"$title\". Priority $priority."
        return SkillReply(
            spoken = spoken,
            display = "Task: $title  ·  $priority",
            event = BrainEvent.TaskAdded(title),
        )
    }
}
