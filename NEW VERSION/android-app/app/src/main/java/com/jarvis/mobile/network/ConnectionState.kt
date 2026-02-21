package com.jarvis.mobile.network

enum class ConnectionType {
    NONE,
    WIFI,
    BLUETOOTH
}

sealed class ConnectionState {
    object Disconnected : ConnectionState()
    object Discovering : ConnectionState()
    object Connecting : ConnectionState()
    data class Connected(val type: ConnectionType, val deviceName: String? = null) : ConnectionState()
    data class Error(val message: String) : ConnectionState()
}
