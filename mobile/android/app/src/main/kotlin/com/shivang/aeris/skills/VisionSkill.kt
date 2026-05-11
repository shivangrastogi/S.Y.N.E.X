package com.shivang.aeris.skills

import com.shivang.aeris.core.brain.BrainEvent
import com.shivang.aeris.core.brain.Skill
import com.shivang.aeris.core.brain.SkillReply
import javax.inject.Inject
import javax.inject.Singleton

/**
 * Voice trigger that simply asks the UI to switch to the Vision tab and run
 * one detection pass. Heavy lifting (camera + MediaPipe) happens in
 * [com.shivang.aeris.vision.ObjectDetector] which the Vision screen owns.
 */
@Singleton
class VisionSkill @Inject constructor() : Skill {
    override val id = "vision.what_is_this"
    override val examples = listOf(
        "what am i holding",
        "yeh kya hai mere haath mein",
        "what do you see",
        "camera mein kya dikh raha hai",
    )

    private val triggers = listOf(
        "what am i holding", "yeh kya hai", "ye kya hai",
        "what do you see", "camera mein kya", "kya dikh raha",
        "snap a photo", "selfie", "tasveer le",
    )

    override fun match(normalized: String): Float =
        if (triggers.any { normalized.contains(it) }) 0.86f else 0f

    override suspend fun handle(normalized: String, raw: String): SkillReply = SkillReply(
        spoken = "Camera kholta hoon sir, ek second.",
        display = "Opening camera…",
        event = BrainEvent.VisionTriggered,
    )
}
