package com.shivang.aeris.skills

import android.content.Context
import android.net.ConnectivityManager
import android.net.NetworkCapabilities
import com.shivang.aeris.core.brain.BrainEvent
import com.shivang.aeris.core.brain.Skill
import com.shivang.aeris.core.brain.SkillReply
import com.shivang.aeris.data.repo.SearchCacheRepo
import com.shivang.aeris.network.WikiClient
import dagger.hilt.android.qualifiers.ApplicationContext
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import javax.inject.Inject
import javax.inject.Singleton

/**
 * Mirrors desktop web_search.py — Wikipedia first, cache results in SQLite,
 * speak short summaries. When offline, only the cache is consulted; if nothing
 * is cached, we explain that the device is offline rather than failing silently.
 */
@Singleton
class WebSearchSkill @Inject constructor(
    @ApplicationContext private val context: Context,
    private val cache: SearchCacheRepo,
    private val wiki: WikiClient,
) : Skill {
    override val id = "web.search"
    override val examples = listOf(
        "search online what is python",
        "tell me more about quantum computing",
        "ai ke baare mein vistar se batao",
    )

    private val triggers = listOf(
        "search online", "search for", "what is", "kya hai",
        "tell me about", "tell me more", "define ", "ke baare mein",
        "vistar se", "in detail", "google ", "look up",
    )

    override fun match(normalized: String): Float =
        if (triggers.any { normalized.contains(it) }) 0.7f else 0f

    override suspend fun handle(normalized: String, raw: String): SkillReply = withContext(Dispatchers.IO) {
        val query = extractQuery(raw)
        if (query.isBlank()) return@withContext SkillReply("Search ke liye topic batao sir.")

        cache.get(query)?.let { hit ->
            return@withContext SkillReply(
                spoken = "Yaad hai sir, pehle search kiya tha. ${hit.summary}",
                display = "${hit.summary}\n\n— cached from ${hit.source}",
                event = BrainEvent.WebSearchDone(query, cached = true),
            )
        }

        if (!isOnline()) return@withContext SkillReply(
            spoken = "Sir, abhi internet nahi hai. Cache mein bhi $query nahi mila.",
            display = "Offline — no cached entry for \"$query\"",
        )

        val hit = wiki.summary(query) ?: return@withContext SkillReply(
            spoken = "Sir, $query ke baare mein kuch khaas nahi mila.",
            display = "No Wikipedia hit for \"$query\"",
        )
        val short = trimToSentences(hit.summary, n = 3)
        cache.put(query, short, hit.source)

        SkillReply(
            spoken = short,
            display = "${hit.title}\n\n${hit.summary}\n\nSource: ${hit.source}",
            event = BrainEvent.WebSearchDone(query, cached = false),
        )
    }

    private fun extractQuery(raw: String): String {
        var q = raw.lowercase()
        for (t in triggers) q = q.replace(t, " ")
        return q.replace(Regex("\\s+"), " ").trim().trim('?', '.', '!')
    }

    private fun trimToSentences(text: String, n: Int): String {
        val parts = text.split(Regex("(?<=[.!?])\\s+"))
        return parts.take(n).joinToString(" ")
    }

    private fun isOnline(): Boolean {
        val cm = context.getSystemService(Context.CONNECTIVITY_SERVICE) as ConnectivityManager
        val nw = cm.activeNetwork ?: return false
        val caps = cm.getNetworkCapabilities(nw) ?: return false
        return caps.hasCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET) &&
            caps.hasCapability(NetworkCapabilities.NET_CAPABILITY_VALIDATED)
    }
}
