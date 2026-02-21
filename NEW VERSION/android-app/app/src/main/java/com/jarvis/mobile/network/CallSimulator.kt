package com.jarvis.mobile.network

import android.Manifest
import android.content.ComponentName
import android.content.Context
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Bundle
import android.telecom.PhoneAccount
import android.telecom.PhoneAccountHandle
import android.telecom.TelecomManager
import android.util.Log
import androidx.core.content.ContextCompat

/**
 * CallSimulator - Utility to simulate incoming calls for testing.
 */
object CallSimulator {
    private const val TAG = "CallSimulator"
    private const val ACCOUNT_ID = "JarvisSimulatorAccount"

    fun simulateIncomingCall(context: Context, name: String, number: String) {
        val telecomManager = context.getSystemService(Context.TELECOM_SERVICE) as TelecomManager
        val componentName = ComponentName(context, JarvisConnectionService::class.java)
        val phoneAccountHandle = PhoneAccountHandle(componentName, ACCOUNT_ID)

        val phoneAccount = PhoneAccount.builder(phoneAccountHandle, "JARVIS Simulator")
            .setCapabilities(PhoneAccount.CAPABILITY_SELF_MANAGED)
            .addSupportedUriScheme(PhoneAccount.SCHEME_TEL)
            .build()
        
        try {
            telecomManager.registerPhoneAccount(phoneAccount)
        } catch (e: Exception) {
            Log.e(TAG, "Account registration failed: ${e.message}")
        }

        val extras = Bundle().apply {
            val uri = Uri.fromParts("tel", if (number == "Unknown") "0000000000" else number, null)
            putParcelable("android.telecom.extra.INCOMING_NUMBER", uri)
            
            // Bridge extras for CallReceiver and ConnectionService
            putString("incoming_number", number)
            putString("phone_number", number)
            putString("caller_name", name)
            
            val gatewayBundle = Bundle().apply {
                putParcelable("gatewayAddress", uri)
            }
            putBundle("android.telecom.extra.GATEWAY_INFO", gatewayBundle)
        }

        try {
            if (ContextCompat.checkSelfPermission(context, Manifest.permission.MANAGE_OWN_CALLS) == PackageManager.PERMISSION_GRANTED) {
                telecomManager.addNewIncomingCall(phoneAccountHandle, extras)
                Log.d(TAG, "Simulated call triggered: $name ($number)")
            }
        } catch (e: Exception) {
            Log.e(TAG, "Simulation failed", e)
        }
    }
}
