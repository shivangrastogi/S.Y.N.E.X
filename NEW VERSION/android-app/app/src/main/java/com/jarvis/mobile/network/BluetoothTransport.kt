package com.jarvis.mobile.network

import android.Manifest
import android.annotation.SuppressLint
import android.bluetooth.BluetoothAdapter
import android.bluetooth.BluetoothDevice
import android.bluetooth.BluetoothManager as AndroidBluetoothManager
import android.bluetooth.BluetoothSocket
import android.content.Context
import android.content.pm.PackageManager
import android.util.Log
import androidx.core.app.ActivityCompat
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import java.io.IOException
import java.io.InputStream
import java.io.OutputStream
import java.util.UUID

@SuppressLint("MissingPermission") // Permissions checked dynamically
class BluetoothTransport(private val context: Context) : Transport {

    private val TAG = "BluetoothTransport"
    override val type = ConnectionType.BLUETOOTH

    private val _state = MutableStateFlow<ConnectionState>(ConnectionState.Disconnected)
    override val state: StateFlow<ConnectionState> = _state.asStateFlow()

    private val bluetoothAdapter: BluetoothAdapter? by lazy {
        val manager = context.getSystemService(Context.BLUETOOTH_SERVICE) as AndroidBluetoothManager
        manager.adapter
    }

    // Standard SPP UUID
    private val SPP_UUID = UUID.fromString("00001101-0000-1000-8000-00805F9B34FB")

    private var socket: BluetoothSocket? = null
    private var inputStream: InputStream? = null
    private var outputStream: OutputStream? = null

    private val scope = CoroutineScope(Dispatchers.IO + SupervisorJob())
    private var readJob: Job? = null
    private var connectJob: Job? = null

    // Configuration
    private val MAX_RETRIES = 3
    private val RETRY_DELAY_MS = 2000L

    override fun connect() {
        if (!hasPermissions()) {
            _state.value = ConnectionState.Error("Missing Bluetooth Permissions")
            return
        }

        if (bluetoothAdapter == null || !bluetoothAdapter!!.isEnabled) {
            _state.value = ConnectionState.Error("Bluetooth disabled")
            return
        }

        if (_state.value is ConnectionState.Connected) return

        _state.value = ConnectionState.Discovering
        
        // Find paired device strategy
        val pairedDevices = bluetoothAdapter?.bondedDevices
        // Prioritize device with "JARVIS" in name, or fallback if user specifically selected one (future)
        val jarvisDevice = pairedDevices?.find { it.name.contains("JARVIS", ignoreCase = true) }

        if (jarvisDevice != null) {
            connectToDevice(jarvisDevice)
        } else {
            _state.value = ConnectionState.Error("No paired device named 'JARVIS' found. Please pair your PC first.")
        }
    }

    private fun connectToDevice(device: BluetoothDevice) {
        connectJob?.cancel()
        connectJob = scope.launch {
            _state.value = ConnectionState.Connecting
            Log.d(TAG, "Attempting connection to ${device.name} (${device.address})")

            var successfulSocket: BluetoothSocket? = null
            
            // RETRY LOOP
            for (attempt in 1..MAX_RETRIES) {
                if (!isActive) break
                
                Log.d(TAG, "Connection Attempt #$attempt")
                
                try {
                    bluetoothAdapter?.cancelDiscovery() // CRITICAL: Always cancel before connect
                    
                    // Strategy 1: Secure RFCOMM by UUID (Standard)
                    try {
                        Log.d(TAG, "Trying Strategy 1: CreateRfcommSocketToServiceRecord (Secure)")
                        val tmp = device.createRfcommSocketToServiceRecord(SPP_UUID)
                        tmp.connect()
                        successfulSocket = tmp
                        Log.d(TAG, "Strategy 1 Succeeded")
                    } catch (e1: IOException) {
                        Log.w(TAG, "Strategy 1 Failed: ${e1.message}")
                        
                        // Strategy 2: Insecure RFCOMM by UUID (Common for non-certified devices)
                        try {
                            Log.d(TAG, "Trying Strategy 2: CreateInsecureRfcommSocketToServiceRecord")
                            val tmp = device.createInsecureRfcommSocketToServiceRecord(SPP_UUID)
                            tmp.connect()
                            successfulSocket = tmp
                            Log.d(TAG, "Strategy 2 Succeeded")
                        } catch (e2: IOException) {
                            Log.w(TAG, "Strategy 2 Failed: ${e2.message}")
                            
                            // Strategy 3: Reflection / Port Fallback (The "Professional" Fix)
                            // Forces connection to Channel 1, bypassing SDP lookup which fails on Windows Python
                            try {
                                Log.d(TAG, "Trying Strategy 3: Reflection (Port 1)")
                                val method = device.javaClass.getMethod("createRfcommSocket", Int::class.javaPrimitiveType)
                                val tmp = method.invoke(device, 1) as BluetoothSocket
                                tmp.connect()
                                successfulSocket = tmp
                                Log.d(TAG, "Strategy 3 (Port 1) Succeeded")
                            } catch (e3: Exception) {
                                Log.e(TAG, "Strategy 3 Failed: ${e3.message}")
                                throw IOException("All connection strategies failed")
                            }
                        }
                    }

                    if (successfulSocket != null) {
                        socket = successfulSocket
                        inputStream = socket!!.inputStream
                        outputStream = socket!!.outputStream
                        
                        _state.value = ConnectionState.Connected(ConnectionType.BLUETOOTH, device.name)
                        Log.i(TAG, "--- BLUETOOTH CONNECTED ---")
                        startReading()
                        break // Success! Exit retry loop
                    }

                } catch (e: Exception) {
                    Log.e(TAG, "Attempt #$attempt failed completely", e)
                    if (attempt < MAX_RETRIES) {
                        _state.value = ConnectionState.Error("Connection Failed (Retrying...)")
                        delay(RETRY_DELAY_MS * attempt) // Exponential-ish backoff
                    } else {
                        _state.value = ConnectionState.Error("Connection Failed: ${e.message}")
                    }
                }
            }
        }
    }

    private fun startReading() {
        readJob?.cancel()
        readJob = scope.launch {
            val buffer = ByteArray(1024)
            Log.d(TAG, "Starting Read Loop")
            
            while (isActive && isConnected()) {
                try {
                    val bytes = inputStream?.read(buffer) ?: -1
                    if (bytes > 0) {
                        val message = String(buffer, 0, bytes)
                        // Simple newline delimiter handling
                        val messages = message.split("\n")
                        for (msg in messages) {
                            if (msg.isNotBlank()) {
                                Log.d(TAG, "RX: $msg")
                                ConnectionManager.handleMessage(msg)
                            }
                        }
                    } else if (bytes == -1) {
                         throw IOException("End of Stream")
                    }
                } catch (e: IOException) {
                    Log.e(TAG, "Read loop error: ${e.message}")
                    disconnect() 
                    break
                }
            }
        }
    }

    override fun disconnect() {
        Log.d(TAG, "Disconnecting Bluetooth...")
        readJob?.cancel()
        connectJob?.cancel()
        
        try {
            socket?.close()
        } catch (e: IOException) {
            Log.e(TAG, "Error closing socket", e)
        }
        
        socket = null
        inputStream = null
        outputStream = null
        
        // Only update state if we were previously connected/connecting to avoid flip-flopping
        if (_state.value !is ConnectionState.Disconnected) {
            _state.value = ConnectionState.Disconnected
        }
    }

    override fun send(message: String) {
        scope.launch {
            try {
                // Ensure newline for delimiting if needed
                val data = if (message.endsWith("\n")) message else "$message\n"
                outputStream?.write(data.toByteArray())
                Log.d(TAG, "TX: $message")
            } catch (e: IOException) {
                Log.e(TAG, "Send failed", e)
                disconnect()
            }
        }
    }

    override fun isConnected(): Boolean {
        return socket?.isConnected == true
    }

    private fun hasPermissions(): Boolean {
         if (android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.S) {
            return ActivityCompat.checkSelfPermission(context, Manifest.permission.BLUETOOTH_CONNECT) == PackageManager.PERMISSION_GRANTED &&
                   ActivityCompat.checkSelfPermission(context, Manifest.permission.BLUETOOTH_SCAN) == PackageManager.PERMISSION_GRANTED
        }
        return true
    }
}
