package com.jarvis.mobile.network

import android.content.Context
import android.util.Log
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.*
import org.json.JSONObject

object ConnectionManager {

    private const val TAG = "ConnectionManager"
    private var context: Context? = null
    private var wifiTransport: WifiTransport? = null
    private var bluetoothTransport: BluetoothTransport? = null
    private var listener: ConnectionListener? = null
    private var service: JarvisMobileService? = null

    // Unify state from multiple transports
    private val _connectionState = MutableStateFlow<ConnectionState>(ConnectionState.Disconnected)
    val connectionState: StateFlow<ConnectionState> = _connectionState.asStateFlow()

    private val _activeTransportType = MutableStateFlow(ConnectionType.NONE)
    val activeTransportType: StateFlow<ConnectionType> = _activeTransportType.asStateFlow()

    private val scope = CoroutineScope(Dispatchers.Main + SupervisorJob())
    private var stateJob: Job? = null

    fun initialize(context: Context) {
        this.context = context.applicationContext
        SettingsManager.initialize(context)
        
        if (wifiTransport == null) wifiTransport = WifiTransport(context)
        if (bluetoothTransport == null) bluetoothTransport = BluetoothTransport(context)
        
        // Handle Auto-Connect
        if (SettingsManager.autoConnectEnabled) {
            autoConnect()
        }
    }

    fun setListener(listener: ConnectionListener) {
        this.listener = listener
    }

    fun setService(service: JarvisMobileService?) {
        this.service = service
    }

    // --- Mode Switching (Exclusive) ---

    fun enableWifiMode() {
        Log.d(TAG, "WiFi Mode Toggle...")
        if (_activeTransportType.value == ConnectionType.WIFI) {
            disconnect()
            return
        }
        
        disconnect() // Clean slate
        _activeTransportType.value = ConnectionType.WIFI
        SettingsManager.lastTransportType = ConnectionType.WIFI.name
        observeTransportState(wifiTransport!!)
        wifiTransport?.connect()
    }

    fun enableBluetoothMode() {
        Log.d(TAG, "Bluetooth Mode Toggle...")
        if (_activeTransportType.value == ConnectionType.BLUETOOTH) {
            disconnect()
            return
        }

        disconnect() // Clean slate
        _activeTransportType.value = ConnectionType.BLUETOOTH
        SettingsManager.lastTransportType = ConnectionType.BLUETOOTH.name
        observeTransportState(bluetoothTransport!!)
        bluetoothTransport?.connect()
    }

    private fun autoConnect() {
        val lastType = SettingsManager.lastTransportType ?: return
        Log.d(TAG, "Attempting Auto-Connect to $lastType")
        when (lastType) {
            ConnectionType.WIFI.name -> enableWifiMode()
            ConnectionType.BLUETOOTH.name -> enableBluetoothMode()
        }
    }

    fun disconnect() {
        Log.d(TAG, "Disconnecting all transports...")
        stopAudioBridge() // Ensure audio is stopped
        
        wifiTransport?.disconnect()
        bluetoothTransport?.disconnect()
        
        // Reset observation logic
        stateJob?.cancel()
        _connectionState.value = ConnectionState.Disconnected
    }
    
    // --- State Observation ---

    private fun observeTransportState(transport: Transport) {
        stateJob?.cancel()
        stateJob = scope.launch {
            transport.state.collect { state ->
                // Relay state to main flow
                _connectionState.value = state
                
                // Update UI/Service
                when (state) {
                    is ConnectionState.Connected -> {
                        listener?.onConnected(state.type)
                        service?.updateStatus("Connected via ${state.type}")
                        
                        // Sync notifications on connect if enabled
                        if (SettingsManager.notificationsEnabled) {
                            scope.launch {
                                NotificationRepository.getUnsent().forEach { notif ->
                                    send(JSONObject().apply {
                                        put("type", "notification")
                                        put("payload", notif)
                                    }.toString())
                                    NotificationRepository.markAsSent(notif.getString("key"))
                                }
                            }
                        }
                    }
                    is ConnectionState.Disconnected -> {
                        listener?.onDisconnected()
                        service?.updateStatus("Disconnected")
                    }
                    is ConnectionState.Error -> {
                        listener?.onError(state.message)
                        service?.updateStatus("Error: ${state.message}")
                    }
                    is ConnectionState.Discovering -> {
                         listener?.onDiscoveryStarted()
                         service?.updateStatus("Searching...")
                    }
                    is ConnectionState.Connecting -> {
                        service?.updateStatus("Connecting...")
                    }
                    else -> {}
                }
            }
        }
    }

    // --- Unified Messaging ---

    fun send(message: String) {
        when (_activeTransportType.value) {
            ConnectionType.WIFI -> wifiTransport?.send(message)
            ConnectionType.BLUETOOTH -> bluetoothTransport?.send(message)
            else -> Log.w(TAG, "Send failed: No active transport")
        }
    }

    fun handleMessage(msg: String) {
        Log.d(TAG, "msg: $msg")
        try {
            val json = JSONObject(msg)
            val type = json.optString("type")
            
            if (type == "command") {
                val command = json.optString("command")
                Log.i(TAG, "Received command: $command")
                
                when (command) {
                    "answer_call" -> {
                        // 1. Try real call
                        CallManager.acceptCall()
                        // 2. Try simulated call
                        JarvisConnectionService.answer()
                    }
                    "decline_call" -> {
                        // 1. Try real call
                        CallManager.declineCall()
                        // 2. Try simulated call
                        JarvisConnectionService.decline()
                    }
                    "unlock" -> {
                        // Handle unlock
                    }
                }
            }
        } catch (e: Exception) {
            Log.e(TAG, "Error parsing message: ${e.message}")
        }
        listener?.onMessageReceived(msg)
    }

    fun isConnected(): Boolean {
        return _connectionState.value is ConnectionState.Connected
    }

    // --- Audio Bridge (Wi-Fi Only) ---
    private var audioBridge: CallAudioBridge? = null

    fun startAudioBridge() {
        if (_activeTransportType.value == ConnectionType.WIFI) {
             val ctx = context ?: return
             if (audioBridge == null) audioBridge = CallAudioBridge(ctx)
             audioBridge?.start()
             Log.d(TAG, "Audio Bridge Started")
        } else {
            Log.w(TAG, "Audio Bridge requires Wi-Fi connection")
        }
    }

    fun stopAudioBridge() {
        audioBridge?.stop()
        audioBridge = null
    }

    fun sendBinary(data: ByteArray) {
        if (_activeTransportType.value == ConnectionType.WIFI) {
            wifiTransport?.sendBinary(data)
        }
    }

    fun onAudioReceived(data: ByteArray) {
        audioBridge?.onAudioReceived(data)
    }
}
