package com.jarvis.mobile.network

import android.content.Context
import android.net.nsd.NsdManager
import android.net.nsd.NsdServiceInfo
import android.os.Build
import android.provider.Settings
import android.util.Log
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import okhttp3.*
import org.json.JSONObject
import java.util.concurrent.TimeUnit

class WifiTransport(private val context: Context) : Transport {

    private val TAG = "WifiTransport"
    override val type = ConnectionType.WIFI
    
    private val _state = MutableStateFlow<ConnectionState>(ConnectionState.Disconnected)
    override val state: StateFlow<ConnectionState> = _state.asStateFlow()

    private var nsdManager: NsdManager? = null
    private var discoveryListener: NsdManager.DiscoveryListener? = null
    private var webSocket: WebSocket? = null
    private val client = OkHttpClient.Builder()
        .readTimeout(0, TimeUnit.MILLISECONDS)
        .build()

    private val scope = CoroutineScope(Dispatchers.IO + SupervisorJob())
    private var heartbeatJob: Job? = null
    
    private val deviceId: String by lazy {
        Settings.Secure.getString(context.contentResolver, Settings.Secure.ANDROID_ID)
    }

    override fun connect() {
        if (_state.value is ConnectionState.Connected || _state.value is ConnectionState.Connecting) return
        
        Log.d(TAG, "Starting Wi-Fi Connection process...")
        _state.value = ConnectionState.Discovering
        startDiscovery()
    }

    override fun disconnect() {
        Log.d(TAG, "Disconnecting Wi-Fi...")
        stopDiscovery()
        stopHeartbeats()
        webSocket?.close(1000, "User disconnected")
        webSocket = null
        _state.value = ConnectionState.Disconnected
    }

    override fun send(message: String) {
        if (isConnected()) {
            webSocket?.send(message)
        } else {
            Log.e(TAG, "Cannot send message, not connected")
        }
    }

    override fun isConnected(): Boolean {
        return _state.value is ConnectionState.Connected
    }

    fun sendBinary(data: ByteArray) {
        if (isConnected()) {
            webSocket?.send(okio.ByteString.of(*data))
        }
    }

    // --- mDNS Discovery ---

    private fun startDiscovery() {
        nsdManager = context.getSystemService(Context.NSD_SERVICE) as NsdManager
        stopDiscovery() // Ensure clean start

        discoveryListener = object : NsdManager.DiscoveryListener {
            override fun onStartDiscoveryFailed(serviceType: String?, errorCode: Int) {
                Log.e(TAG, "Discovery failed: $errorCode")
                _state.value = ConnectionState.Error("Discovery Failed: $errorCode")
            }

            override fun onStopDiscoveryFailed(serviceType: String?, errorCode: Int) {
                Log.e(TAG, "Stop Discovery failed: $errorCode")
            }

            override fun onDiscoveryStarted(serviceType: String?) {
                Log.d(TAG, "Discovery started")
            }

            override fun onDiscoveryStopped(serviceType: String?) {
                Log.d(TAG, "Discovery stopped")
            }

            override fun onServiceFound(serviceInfo: NsdServiceInfo) {
                if (serviceInfo.serviceType.contains("_jarvis")) {
                    Log.d(TAG, "Service found: ${serviceInfo.serviceName}")
                    nsdManager?.resolveService(serviceInfo, object : NsdManager.ResolveListener {
                        override fun onResolveFailed(serviceInfo: NsdServiceInfo?, errorCode: Int) {
                            Log.e(TAG, "Resolve failed: $errorCode")
                        }

                        override fun onServiceResolved(serviceInfo: NsdServiceInfo) {
                            Log.d(TAG, "Service resolved: ${serviceInfo.host.hostAddress}:${serviceInfo.port}")
                            stopDiscovery() // Found it, stop looking
                            _state.value = ConnectionState.Connecting
                            connectWebSocket(serviceInfo.host.hostAddress!!, serviceInfo.port)
                        }
                    })
                }
            }

            override fun onServiceLost(serviceInfo: NsdServiceInfo?) {
                Log.e(TAG, "Service lost")
            }
        }

        try {
            nsdManager?.discoverServices("_jarvis._tcp.", NsdManager.PROTOCOL_DNS_SD, discoveryListener)
        } catch (e: Exception) {
            Log.e(TAG, "Error starting discovery: ${e.message}")
            _state.value = ConnectionState.Error("Discovery Error: ${e.message}")
        }
    }

    private fun stopDiscovery() {
        discoveryListener?.let {
            try {
                nsdManager?.stopServiceDiscovery(it)
            } catch (e: Exception) {
                // Ignore if not running
            }
        }
        discoveryListener = null
    }

    // --- WebSocket ---

    private fun connectWebSocket(ip: String, port: Int) {
        val url = "ws://$ip:$port/ws"
        val request = Request.Builder().url(url).build()

        webSocket = client.newWebSocket(request, object : WebSocketListener() {
            override fun onOpen(webSocket: WebSocket, response: Response) {
                Log.d(TAG, "WebSocket Connected")
                _state.value = ConnectionState.Connected(ConnectionType.WIFI, "JARVIS ($ip)")
                
                // Register
                sendRegistration()
                startHeartbeats()
            }

            override fun onMessage(webSocket: WebSocket, text: String) {
                ConnectionManager.handleMessage(text)
            }

            override fun onMessage(webSocket: WebSocket, bytes: okio.ByteString) {
                ConnectionManager.onAudioReceived(bytes.toByteArray())
            }

            override fun onClosing(webSocket: WebSocket, code: Int, reason: String) {
                Log.d(TAG, "WebSocket Closing: $reason")
                webSocket.close(1000, null)
            }
            
            override fun onClosed(webSocket: WebSocket, code: Int, reason: String) {
                Log.d(TAG, "WebSocket Closed")
                stopHeartbeats()
                if (_state.value is ConnectionState.Connected) {
                     _state.value = ConnectionState.Disconnected
                     // Auto-reconnect uses logic in ConnectionManager or we can trigger here
                     // For now, let's treat it as disconnected.
                     // The user requirement says "Auto reconnect ONLY if Wi-Fi mode enabled"
                     // We will implement auto-reconnect logic in this Transport if needed, 
                     // or rely on the manager to re-trigger connect().
                     // Let's internally try to recover if we were connected.
                     
                     // But strictly speaking, if socket closes, we go to Disconnected.
                     // The Manager can decide to re-enable.
                }
            }

            override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {
                Log.e(TAG, "WebSocket Failure: ${t.message}")
                stopHeartbeats()
                _state.value = ConnectionState.Error("Connection Failed: ${t.message}")
            }
        })
    }

    private fun sendRegistration() {
        val json = JSONObject().apply {
            put("type", "registration")
            put("payload", JSONObject().apply {
                put("device_id", deviceId)
                put("device_name", "${Build.MANUFACTURER} ${Build.MODEL}")
                put("app_version", "2.0")
            })
        }
        send(json.toString())
    }

    private fun startHeartbeats() {
        stopHeartbeats()
        heartbeatJob = scope.launch {
            while (isActive) {
                delay(15000) // 15 seconds
                if (isConnected()) {
                    val hb = JSONObject().apply { put("type", "heartbeat") }
                    send(hb.toString())
                } else {
                    break
                }
            }
        }
    }

    private fun stopHeartbeats() {
        heartbeatJob?.cancel()
        heartbeatJob = null
    }
}
