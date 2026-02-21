package com.jarvis.mobile.network

import android.telecom.Connection
import android.telecom.ConnectionRequest
import android.telecom.ConnectionService
import android.telecom.PhoneAccountHandle
import android.telecom.TelecomManager
import android.util.Log
import org.json.JSONObject

/**
 * JarvisConnectionService - Handles self-managed connections for call simulation.
 * This allows the app to respond to answer/decline commands for simulated calls.
 */
class JarvisConnectionService : ConnectionService() {
    
    companion object {
        private const val TAG = "JarvisCS"
        var activeConnection: Connection? = null

        fun answer() {
            Log.d(TAG, "Answering connection: $activeConnection")
            activeConnection?.onAnswer()
        }

        fun decline() {
            Log.d(TAG, "Declining connection: $activeConnection")
            activeConnection?.onDisconnect()
        }
    }

    override fun onCreateIncomingConnection(
        connectionManagerPhoneAccount: PhoneAccountHandle?,
        request: ConnectionRequest?
    ): Connection {
        Log.d(TAG, "onCreateIncomingConnection")
        
        val connection = object : Connection() {
            override fun onAnswer() {
                Log.d(TAG, "Connection Answered")
                setActive()
                ConnectionManager.startAudioBridge()
                sendUpdate("active")
            }

            override fun onDisconnect() {
                Log.d(TAG, "Connection Disconnected")
                setDisconnected(android.telecom.DisconnectCause(android.telecom.DisconnectCause.LOCAL))
                destroy()
                activeConnection = null
                ConnectionManager.stopAudioBridge()
                sendUpdate("ended")
            }

            override fun onAbort() {
                onDisconnect()
            }

            override fun onReject() {
                onDisconnect()
            }
            
            private fun sendUpdate(status: String) {
                val extras = request?.extras
                val name = extras?.getString("caller_name") ?: "Unknown"
                val number = extras?.getString("incoming_number") ?: "Unknown"
                
                val payload = JSONObject().apply {
                    put("name", name)
                    put("number", number)
                    put("status", status)
                    put("source", "simulator")
                }
                ConnectionManager.send(JSONObject().apply {
                    put("type", "incoming_call")
                    put("payload", payload)
                }.toString())
            }
        }

        connection.setAddress(request?.address, TelecomManager.PRESENTATION_ALLOWED)
        connection.setInitializing()
        
        // Report the incoming call immediately
        val extras = request?.extras
        val name = extras?.getString("caller_name") ?: "Tony Stark"
        val number = extras?.getString("incoming_number") ?: "555-0199"
        
        Log.d(TAG, "Reporting simulated call: $name ($number)")
        
        val payload = JSONObject().apply {
            put("name", name)
            put("number", number)
            put("status", "ringing")
            put("source", "simulator")
        }
        ConnectionManager.send(JSONObject().apply {
            put("type", "incoming_call")
            put("payload", payload)
        }.toString())

        activeConnection = connection
        return connection
    }

    override fun onCreateIncomingConnectionFailed(
        connectionManagerPhoneAccount: PhoneAccountHandle?,
        request: ConnectionRequest?
    ) {
        Log.e(TAG, "onCreateIncomingConnectionFailed")
        super.onCreateIncomingConnectionFailed(connectionManagerPhoneAccount, request)
    }
}
