package com.shivang.aeris.network

import okhttp3.OkHttpClient
import okhttp3.Request
import org.json.JSONObject
import java.net.URLEncoder
import java.util.concurrent.TimeUnit
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class WikiClient @Inject constructor() {
    private val http = OkHttpClient.Builder()
        .connectTimeout(4, TimeUnit.SECONDS)
        .readTimeout(6, TimeUnit.SECONDS)
        .build()

    /** Returns the Wikipedia REST summary, or null when offline / not found. */
    fun summary(query: String): Hit? = runCatching {
        val q = URLEncoder.encode(query.trim().replace(' ', '_'), "UTF-8")
        val req = Request.Builder()
            .url("https://en.wikipedia.org/api/rest_v1/page/summary/$q")
            .header("User-Agent", "AERIS-Mobile/0.1")
            .build()
        http.newCall(req).execute().use { r ->
            if (!r.isSuccessful) return@use null
            val body = r.body?.string() ?: return@use null
            val obj = JSONObject(body)
            val extract = obj.optString("extract").takeIf { it.isNotBlank() } ?: return@use null
            Hit(title = obj.optString("title", query), summary = extract,
                source = obj.optJSONObject("content_urls")
                    ?.optJSONObject("desktop")?.optString("page") ?: "wikipedia")
        }
    }.getOrNull()

    data class Hit(val title: String, val summary: String, val source: String)
}
