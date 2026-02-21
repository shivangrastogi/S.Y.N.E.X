package com.jarvis.mobile.network

import kotlinx.coroutines.flow.StateFlow

interface Transport {
    val type: ConnectionType
    val state: StateFlow<ConnectionState>
    
    fun connect()
    fun disconnect()
    fun send(message: String)
    fun isConnected(): Boolean
}
