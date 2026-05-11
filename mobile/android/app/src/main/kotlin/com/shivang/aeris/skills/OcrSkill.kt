package com.shivang.aeris.skills

import com.shivang.aeris.core.brain.Skill
import com.shivang.aeris.core.brain.SkillReply
import javax.inject.Inject
import javax.inject.Singleton

/**
 * "snip and read" / "screen ka text padho" — UI captures, then calls
 * [com.shivang.aeris.vision.OcrEngine] (MLKit text recognition).
 *
 * This skill just routes the trigger; actual OCR happens in the Vision tab.
 */
@Singleton
class OcrSkill @Inject constructor() : Skill {
    override val id = "vision.ocr"
    override val examples = listOf("snip and read", "screen ka text padho", "read this text")

    private val triggers = listOf(
        "snip and read", "read text", "ocr", "text padho",
        "screen ka text", "padh ke sunao",
    )

    override fun match(normalized: String): Float =
        if (triggers.any { normalized.contains(it) }) 0.86f else 0f

    override suspend fun handle(normalized: String, raw: String): SkillReply = SkillReply(
        spoken = "Camera kholiye, jo padhna hai uspe focus karenge sir.",
        display = "Open Vision tab → tap text-recognize",
    )
}
