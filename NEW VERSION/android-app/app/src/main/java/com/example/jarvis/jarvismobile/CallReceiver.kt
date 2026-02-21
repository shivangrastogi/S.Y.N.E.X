package com.example.jarvis.jarvismobile

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.telephony.TelephonyManager
import android.util.Log
import com.jarvis.mobile.network.ConnectionManager
import org.json.JSONObject

class CallReceiver : BroadcastReceiver() {
    companion object {
        private const val TAG = "CallReceiver"
        private var lastState = TelephonyManager.CALL_STATE_IDLE
    }

    override fun onReceive(context: Context, intent: Intent) {
        if (intent.action == "android.intent.action.PHONE_STATE") {
            val stateStr = intent.getStringExtra(TelephonyManager.EXTRA_STATE)
            
            // 1. Try standard extra
            var number = intent.getStringExtra(TelephonyManager.EXTRA_INCOMING_NUMBER)
            
            // 2. Try simulated extras (bridge from CallSimulator)
            if (number == null) {
                number = intent.getStringExtra("incoming_number") ?: intent.getStringExtra("phone_number")
            }
            
            val simulatedName = intent.getStringExtra("caller_name")

            var state = TelephonyManager.CALL_STATE_IDLE
            if (stateStr == TelephonyManager.EXTRA_STATE_RINGING) {
                state = TelephonyManager.CALL_STATE_RINGING
            } else if (stateStr == TelephonyManager.EXTRA_STATE_OFFHOOK) {
                state = TelephonyManager.CALL_STATE_OFFHOOK
            }

            // Fallback: Query CallLog only if not simulated
            if (state == TelephonyManager.CALL_STATE_RINGING && number == null) {
                number = getLatestCallNumber(context)
            }

            // Resolve Contact Name (Simulated name takes priority for testing)
            val contactName = simulatedName ?: if (number != null) getContactName(context, number) else null

            onCallStateChanged(context, state, number, contactName)
        }
    }

    private fun getContactName(context: Context, phoneNumber: String): String? {
        if (androidx.core.content.ContextCompat.checkSelfPermission(
                context, android.Manifest.permission.READ_CONTACTS
            ) != android.content.pm.PackageManager.PERMISSION_GRANTED) {
            return null
        }
        
        val uri = android.net.Uri.withAppendedPath(
            android.provider.ContactsContract.PhoneLookup.CONTENT_FILTER_URI,
            android.net.Uri.encode(phoneNumber)
        )
        
        val projection = arrayOf(android.provider.ContactsContract.PhoneLookup.DISPLAY_NAME)
        
        try {
            val cursor = context.contentResolver.query(uri, projection, null, null, null)
            cursor?.use {
                if (it.moveToFirst()) {
                    val nameIndex = it.getColumnIndex(android.provider.ContactsContract.PhoneLookup.DISPLAY_NAME)
                    if (nameIndex != -1) return it.getString(nameIndex)
                }
            }
        } catch (e: Exception) {
            Log.e(TAG, "Error looking up contact", e)
        }
        return null
    }

    private fun getLatestCallNumber(context: Context): String? {
        if (androidx.core.content.ContextCompat.checkSelfPermission(
                context, android.Manifest.permission.READ_CALL_LOG
            ) != android.content.pm.PackageManager.PERMISSION_GRANTED) {
            return null
        }

        try {
            val cursor = context.contentResolver.query(
                android.provider.CallLog.Calls.CONTENT_URI,
                arrayOf(android.provider.CallLog.Calls.NUMBER, android.provider.CallLog.Calls.DATE),
                null, null,
                android.provider.CallLog.Calls.DATE + " DESC"
            )
            
            cursor?.use {
                if (it.moveToFirst()) {
                    val dateIndex = it.getColumnIndex(android.provider.CallLog.Calls.DATE)
                    if (dateIndex != -1) {
                        val callDate = it.getLong(dateIndex)
                        if (Math.abs(System.currentTimeMillis() - callDate) < 10000) {
                            val numberIndex = it.getColumnIndex(android.provider.CallLog.Calls.NUMBER)
                            if (numberIndex != -1) return it.getString(numberIndex)
                        }
                    }
                }
            }
        } catch (e: Exception) {
            Log.e(TAG, "Error querying CallLog", e)
        }
        return null
    }

    private fun onCallStateChanged(context: Context, state: Int, number: String?, name: String?) {
        if (lastState == state) return
        
        when (state) {
            TelephonyManager.CALL_STATE_RINGING -> {
                val displayNumber = number ?: "Unknown Number"
                val displayCaller = name ?: displayNumber
                Log.d(TAG, "Incoming call from: $displayCaller ($displayNumber)")
                sendCallEvent(displayNumber, displayCaller, "ringing")
            }
            TelephonyManager.CALL_STATE_OFFHOOK -> {
                Log.d(TAG, "Call answered")
                ConnectionManager.startAudioBridge()
                sendCallEvent("", "", "active")
            }
            TelephonyManager.CALL_STATE_IDLE -> {
                Log.d(TAG, "Call ended")
                ConnectionManager.stopAudioBridge()
                sendCallEvent("", "", "ended")
            }
        }
        lastState = state
    }

    private fun sendCallEvent(number: String, caller: String, status: String) {
        val payload = JSONObject().apply {
            put("type", "incoming_call")
            put("payload", JSONObject().apply {
                put("name", caller)
                put("number", number)
                put("status", status)
                put("source", "receiver")
            })
        }
        ConnectionManager.send(payload.toString())
    }
}
