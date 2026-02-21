package com.jarvis.mobile.network

import android.Manifest
import android.content.Context
import android.content.pm.PackageManager
import android.database.Cursor
import android.net.Uri
import android.provider.CallLog
import android.provider.ContactsContract
import android.telecom.Call
import android.telecom.InCallService
import android.util.Log
import androidx.core.content.ContextCompat
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import org.json.JSONObject

data class CallInfo(
    val name: String = "Unknown",
    val number: String = "",
    val status: String = "Disconnected"
)

/**
 * CallManager - The primary InCallService for handling real system calls.
 * This service is only active if the app is the Default Dialer.
 */
class CallManager : InCallService() {
    
    private val TAG = "CallManager"
    private val serviceScope = CoroutineScope(Dispatchers.Main + SupervisorJob())
    
    companion object {
        var activeCall: Call? = null
        
        // Observable State
        private val _callState = MutableStateFlow(CallInfo())
        val callState: StateFlow<CallInfo> = _callState.asStateFlow()
        
        fun acceptCall() {
            Log.d("CallManager", "acceptCall() - Active: $activeCall, State: ${activeCall?.state}")
            activeCall?.answer(0)
        }
        
        fun declineCall() {
            Log.d("CallManager", "declineCall() - Active: $activeCall, State: ${activeCall?.state}")
            if (activeCall?.state == Call.STATE_RINGING) {
                activeCall?.reject(false, null)
            } else {
                activeCall?.disconnect()
            }
        }
    }

    override fun onCreate() {
        super.onCreate()
        Log.d(TAG, "InCallService Created")
        ConnectionManager.initialize(this)
    }

    override fun onCallAdded(call: Call) {
        super.onCallAdded(call)
        activeCall = call
        Log.d(TAG, "Real Call Added: $call")
        
        call.registerCallback(object : Call.Callback() {
            override fun onStateChanged(call: Call, state: Int) {
                Log.d(TAG, "Call State Changed: $state")
                handleCallState(call, state)
            }
        })
        
        // Sometimes details aren't ready immediately, try again in a few ms
        handleCallState(call, call.state)
        serviceScope.launch {
            delay(500)
            if (activeCall == call) handleCallState(call, call.state)
        }
    }

    override fun onCallRemoved(call: Call) {
        super.onCallRemoved(call)
        Log.d(TAG, "Real Call Removed")
        
        val number = extractNumber(call)
        val name = getContactName(this, number) ?: number
        sendCallUpdate(name, number, "ended")
        
        activeCall = null
        ConnectionManager.stopAudioBridge()
        _callState.value = CallInfo(status = "Disconnected")
    }

    private fun handleCallState(call: Call, state: Int) {
        val number = extractNumber(call)
        val name = getContactName(this, number) ?: number
        
        Log.d(TAG, "Handling state $state for $name ($number)")
        
        var statusStr = "Unknown"
        when (state) {
            Call.STATE_RINGING -> {
                statusStr = "Ringing"
                sendCallUpdate(name, number, "ringing")
            }
            Call.STATE_ACTIVE -> {
                statusStr = "Active"
                sendCallUpdate(name, number, "active")
                ConnectionManager.startAudioBridge()
            }
            Call.STATE_DISCONNECTED -> {
                statusStr = "Disconnected"
                ConnectionManager.stopAudioBridge()
                sendCallUpdate(name, number, "ended")
            }
            Call.STATE_CONNECTING -> statusStr = "Connecting"
            Call.STATE_DIALING -> statusStr = "Dialing"
            Call.STATE_HOLDING -> statusStr = "On Hold"
        }
        
        _callState.value = CallInfo(name, number, statusStr)
    }

    private fun extractNumber(call: Call): String {
        // 1. Try Handle
        var number = call.details.handle?.schemeSpecificPart
        if (isValidNumber(number)) return number!!

        // 2. Try Gateway
        number = call.details.gatewayInfo?.originalAddress?.schemeSpecificPart
        if (isValidNumber(number)) return number!!

        // 3. Try Intent Extras
        val extras = call.details.intentExtras
        if (extras != null) {
            val keys = arrayOf(
                "android.telecom.extra.INCOMING_NUMBER",
                "incoming_number",
                "phone_number",
                "android.phone.extra.ORIGINAL_PHONE_NUMBER"
            )
            for (key in keys) {
                number = extras.getString(key)
                if (isValidNumber(number)) return number!!
            }
        }

        // 4. Try CallLog Fallback (if ringing)
        if (call.state == Call.STATE_RINGING) {
            number = tryFallBackToCallLog()
            if (isValidNumber(number)) return number!!
        }

        return "Unknown Number"
    }

    private fun isValidNumber(number: String?): Boolean {
        return !number.isNullOrBlank() && 
               number != "null" && 
               number != "Unknown" && 
               number != "Unknown Number" &&
               number != "0000000000"
    }

    private fun tryFallBackToCallLog(): String? {
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.READ_CALL_LOG) 
            != PackageManager.PERMISSION_GRANTED) return null
            
        try {
            // Only consider recent logs (last 30 seconds) to avoid stale data
            val cursor = contentResolver.query(
                CallLog.Calls.CONTENT_URI,
                arrayOf(CallLog.Calls.NUMBER, CallLog.Calls.DATE),
                null, null,
                "${CallLog.Calls.DATE} DESC LIMIT 1"
            )
            cursor?.use {
                if (it.moveToFirst()) {
                    val number = it.getString(0)
                    val date = it.getLong(1)
                    val age = System.currentTimeMillis() - date
                    if (age < 30000) { // 30 seconds
                        Log.d(TAG, "Found recent CallLog entry: $number (${age/1000}s old)")
                        return number
                    } else {
                        Log.d(TAG, "Latest CallLog entry is too old: ${age/1000}s")
                    }
                }
            }
        } catch (e: Exception) {
            Log.e(TAG, "CallLog query failed: ${e.message}")
        }
        return null
    }

    private fun getContactName(context: Context, phoneNumber: String): String? {
        if (!isValidNumber(phoneNumber) || phoneNumber == "Unknown Number") return null
        try {
            if (ContextCompat.checkSelfPermission(context, Manifest.permission.READ_CONTACTS) 
                != PackageManager.PERMISSION_GRANTED) return null
            
            val uri = Uri.withAppendedPath(ContactsContract.PhoneLookup.CONTENT_FILTER_URI, Uri.encode(phoneNumber))
            val projection = arrayOf(ContactsContract.PhoneLookup.DISPLAY_NAME)
            context.contentResolver.query(uri, projection, null, null, null)?.use { cursor ->
                if (cursor.moveToFirst()) return cursor.getString(0)
            }
        } catch (e: Exception) {
            Log.e(TAG, "Contact lookup failed: ${e.message}")
        }
        return null
    }
    
    private fun sendCallUpdate(name: String, number: String, status: String) {
        val payload = JSONObject().apply {
            put("name", name)
            put("number", number)
            put("status", status)
            put("source", "incall")
        }
        ConnectionManager.send(JSONObject().apply {
            put("type", "incoming_call")
            put("payload", payload)
        }.toString())
    }

    override fun onDestroy() {
        serviceScope.cancel()
        super.onDestroy()
    }
}
