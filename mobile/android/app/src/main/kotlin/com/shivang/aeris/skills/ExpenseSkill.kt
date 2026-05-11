package com.shivang.aeris.skills

import com.shivang.aeris.core.brain.BrainEvent
import com.shivang.aeris.core.brain.Skill
import com.shivang.aeris.core.brain.SkillReply
import com.shivang.aeris.data.repo.WorkbookRepo
import javax.inject.Inject
import javax.inject.Singleton

/** "500 rupees food pe kharch kiye" → adds expense + speaks confirmation. */
@Singleton
class ExpenseSkill @Inject constructor(
    private val repo: WorkbookRepo,
) : Skill {
    override val id = "expense.add"
    override val examples = listOf(
        "500 rupees food pe kharch kiye",
        "750 ka uber lagaya",
        "200 rs grocery spent",
    )

    private val triggerWords = listOf(
        "kharch", "spent", "spend", "lagaya", "lagaye", "lagayi",
        "kharcha", "expense", "paid", "diya rupees",
    )

    private val categoryHints = mapOf(
        "Food & Dining" to listOf("food", "khana", "lunch", "dinner", "breakfast", "swiggy", "zomato", "restaurant", "cafe"),
        "Transport" to listOf("uber", "ola", "rapido", "auto", "taxi", "metro", "bus", "petrol", "diesel", "fuel"),
        "Groceries" to listOf("grocery", "groceries", "sabzi", "kirana", "blinkit", "zepto", "bigbasket"),
        "Utilities" to listOf("bill", "electricity", "water", "internet", "wifi", "recharge"),
        "Entertainment" to listOf("movie", "netflix", "spotify", "prime", "hotstar", "concert"),
        "Shopping" to listOf("amazon", "flipkart", "myntra", "shopping", "kapde", "clothes"),
        "Health" to listOf("doctor", "medicine", "dawai", "hospital", "pharmacy"),
        "Education" to listOf("book", "kitaab", "course", "udemy", "coursera", "fees"),
        "Travel" to listOf("flight", "train", "irctc", "hotel", "trip", "vacation"),
    )

    override fun match(normalized: String): Float {
        val hasAmount = Regex("\\b\\d+\\b").containsMatchIn(normalized)
        val hasTrigger = triggerWords.any { normalized.contains(it) }
        return if (hasAmount && hasTrigger) 0.92f else 0f
    }

    override suspend fun handle(normalized: String, raw: String): SkillReply {
        val amount = Regex("\\b(\\d+)\\b").find(normalized)?.groupValues?.get(1)?.toIntOrNull()
            ?: return SkillReply("Amount samajh nahi aaya sir.")
        val category = categoryHints.entries.firstOrNull { (_, kws) ->
            kws.any { normalized.contains(it) }
        }?.key ?: "Misc"

        repo.addExpense(amount, category, note = raw)

        val spoken = "Theek hai sir. ₹$amount $category mein add kar diya."
        return SkillReply(
            spoken = spoken,
            display = "₹$amount → $category",
            event = BrainEvent.ExpenseAdded(amount, category),
        )
    }
}
