package com.shivang.aeris.skills

import com.shivang.aeris.core.brain.Skill
import com.shivang.aeris.core.brain.SkillReply
import com.shivang.aeris.data.repo.WorkbookRepo
import kotlinx.coroutines.flow.first
import javax.inject.Inject
import javax.inject.Singleton

/** "is mahine kitna kharcha" → speaks total + top categories. */
@Singleton
class MonthSummarySkill @Inject constructor(
    private val repo: WorkbookRepo,
) : Skill {
    override val id = "expense.summary"
    override val examples = listOf("is mahine kitna kharcha", "month summary")

    private val triggers = listOf(
        "is mahine kitna", "month summary", "mahine kharcha",
        "kitna kharcha", "month spend", "monthly spending",
    )

    override fun match(normalized: String): Float =
        if (triggers.any { normalized.contains(it) }) 0.9f else 0f

    override suspend fun handle(normalized: String, raw: String): SkillReply {
        val total = repo.observeMonthSpend().first()
        val breakdown = repo.monthBreakdown().take(3)
        val top = if (breakdown.isEmpty()) "" else
            " Top: " + breakdown.joinToString(", ") { "${it.cat} ₹${it.total}" }
        val spoken = "Is mahine total ₹$total kharch hua hai sir.$top"
        return SkillReply(spoken = spoken, display = spoken)
    }
}
