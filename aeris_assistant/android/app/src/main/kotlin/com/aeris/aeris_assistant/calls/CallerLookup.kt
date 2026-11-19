package com.aeris.aeris_assistant.calls

import android.Manifest
import android.content.Context
import android.content.pm.PackageManager
import android.net.Uri
import android.provider.CallLog
import android.provider.ContactsContract
import android.util.Log

/**
 * "Whose number is this?" via Android's own PhoneLookup index — one indexed
 * query (milliseconds), and it understands every number format (+91, 0-prefix,
 * spaces). Loading the whole contact list in Dart instead took longer than
 * the phone rings (found on the phone, 2026-11-17).
 */
object CallerLookup {
    /** The saved contact's display name, or null (unknown number / no permission). */
    fun nameFor(context: Context, number: String): String? {
        if (number.isBlank()) return null
        if (context.checkSelfPermission(Manifest.permission.READ_CONTACTS) != PackageManager.PERMISSION_GRANTED) {
            return null
        }
        return try {
            val uri = Uri.withAppendedPath(ContactsContract.PhoneLookup.CONTENT_FILTER_URI, Uri.encode(number))
            context.contentResolver.query(uri, arrayOf(ContactsContract.PhoneLookup.DISPLAY_NAME), null, null, null)
                ?.use { cursor -> if (cursor.moveToFirst()) cursor.getString(0) else null }
        } catch (e: Exception) {
            Log.w("AerisCalls", "caller lookup failed: $e")
            null
        }
    }

    /**
     * The people most likely to call: starred contacts first, then whoever
     * called (answered, missed or declined) in the last [days] days, most
     * calls first. Names exactly as [nameFor] returns them, so a pre-made
     * announcement matches the one a real call asks for.
     */
    fun likelyCallers(context: Context, limit: Int, days: Int = 90): List<String> {
        val score = LinkedHashMap<String, Int>()
        fun add(name: String?, points: Int) {
            val clean = name?.trim().orEmpty()
            if (clean.isNotEmpty()) score[clean] = (score[clean] ?: 0) + points
        }
        if (has(context, Manifest.permission.READ_CONTACTS)) {
            try {
                context.contentResolver.query(
                    ContactsContract.Contacts.CONTENT_URI,
                    arrayOf(ContactsContract.Contacts.DISPLAY_NAME),
                    "${ContactsContract.Contacts.STARRED} = 1", null, null,
                )?.use { cursor -> while (cursor.moveToNext()) add(cursor.getString(0), 1000) }
            } catch (e: Exception) {
                Log.w("AerisCalls", "starred contacts failed: $e")
            }
        }
        if (has(context, Manifest.permission.READ_CALL_LOG)) {
            val since = System.currentTimeMillis() - days * 24L * 60 * 60 * 1000
            val incomingTypes = setOf(CallLog.Calls.INCOMING_TYPE, CallLog.Calls.MISSED_TYPE, CallLog.Calls.REJECTED_TYPE)
            try {
                context.contentResolver.query(
                    CallLog.Calls.CONTENT_URI,
                    arrayOf(CallLog.Calls.CACHED_NAME, CallLog.Calls.TYPE),
                    "${CallLog.Calls.DATE} > ?", arrayOf(since.toString()), "${CallLog.Calls.DATE} DESC",
                )?.use { cursor ->
                    while (cursor.moveToNext()) if (cursor.getInt(1) in incomingTypes) add(cursor.getString(0), 1)
                }
            } catch (e: Exception) {
                Log.w("AerisCalls", "call history failed: $e")
            }
        }
        return score.entries.sortedByDescending { it.value }.take(limit).map { it.key }
    }

    private fun has(context: Context, permission: String) =
        context.checkSelfPermission(permission) == PackageManager.PERMISSION_GRANTED
}
