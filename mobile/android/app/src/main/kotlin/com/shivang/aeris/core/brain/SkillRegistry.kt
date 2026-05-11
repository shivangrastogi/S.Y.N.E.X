package com.shivang.aeris.core.brain

import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class SkillRegistry @Inject constructor(
    skills: Set<@JvmSuppressWildcards Skill>,
) {
    val skills: List<Skill> = skills.toList()

    fun bestMatch(normalized: String, threshold: Float = 0.55f): Skill? {
        var best: Skill? = null
        var bestScore = 0f
        for (s in skills) {
            val sc = s.match(normalized)
            if (sc > bestScore) { best = s; bestScore = sc }
        }
        return if (bestScore >= threshold) best else null
    }
}
