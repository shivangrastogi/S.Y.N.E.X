package com.shivang.aeris.core.brain

import com.shivang.aeris.core.llm.LlmEngine
import com.shivang.aeris.core.normalizer.HinglishNormalizer
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.flow
import kotlinx.coroutines.flow.flowOf
import javax.inject.Inject
import javax.inject.Singleton

/**
 * Two-stage router (mirrors desktop core/brain.py):
 *   1. Try a fast deterministic skill match — no model needed.
 *   2. Fall back to the on-device LLM for free-form chat.
 *
 * Streaming so the UI can render LLM tokens as they arrive.
 */
@Singleton
class Brain @Inject constructor(
    private val registry: SkillRegistry,
    private val llm: LlmEngine,
) {
    sealed interface Reply {
        data class Skill(val reply: SkillReply) : Reply
        data class LlmStream(val tokens: Flow<String>) : Reply
        data class Error(val message: String) : Reply
    }

    suspend fun route(raw: String): Reply {
        val text = raw.trim()
        if (text.isEmpty()) return Reply.Error("Kuch sunaai nahi diya")
        val norm = HinglishNormalizer.normalize(text)

        registry.bestMatch(norm)?.let { skill ->
            return Reply.Skill(skill.handle(norm, text))
        }

        if (!llm.isReady()) {
            return Reply.Skill(
                SkillReply(
                    spoken = "Brain model load nahi hai sir. Settings mein .task file ka path daal dijiye.",
                    display = "On-device model not loaded. Open Settings → Brain model and pick a Gemma .task file.",
                )
            )
        }

        val prompt = buildChatPrompt(text)
        return Reply.LlmStream(llm.generateStream(prompt))
    }

    private fun buildChatPrompt(userText: String): String = """
        <start_of_turn>user
        You are A.E.R.I.S. — a Hinglish personal assistant on Shivang's Android phone.
        Reply in the same language mix the user used (Hindi roman + English is fine).
        Be concise — 1 to 3 sentences. Never say you are an AI model.

        User: $userText
        <end_of_turn>
        <start_of_turn>model
    """.trimIndent()

    /** Convenience for skills that want to delegate sub-questions to the LLM. */
    fun llmChat(userText: String): Flow<String> =
        if (llm.isReady()) llm.generateStream(buildChatPrompt(userText))
        else flowOf("Brain model not loaded.")
}
