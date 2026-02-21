package com.jarvis.mobile.network

interface ConnectionListener {
    fun onConnected(type: ConnectionType)
    fun onDisconnected()
    fun onMessageReceived(message: String)
    fun onError(error: String)
    fun onConnectionFailed(error: String)
    fun onDiscoveryStarted()
    fun onDeviceFound(name: String, ip: String, port: Int, path: String)
}
