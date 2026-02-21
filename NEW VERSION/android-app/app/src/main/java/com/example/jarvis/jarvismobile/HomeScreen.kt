package com.example.jarvis.jarvismobile

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.jarvis.mobile.network.CallSimulator
import com.jarvis.mobile.network.ConnectionManager
import com.jarvis.mobile.network.ConnectionType

@Composable
fun JarvisHomeScreen(
    connectionStatus: String,
    isConnected: Boolean,
    activeTransport: ConnectionType,
    onSettingsClick: () -> Unit
) {
    val context = LocalContext.current
    
    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(Brush.verticalGradient(listOf(MaterialTheme.colorScheme.background, MaterialTheme.colorScheme.surface)))
            .padding(24.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.spacedBy(24.dp)
    ) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Text(
                text = "JARVIS Assistant",
                fontSize = 28.sp,
                fontWeight = FontWeight.Bold,
                color = MaterialTheme.colorScheme.onBackground
            )
            IconButton(onClick = onSettingsClick) {
                Icon(
                    imageVector = androidx.compose.material.icons.Icons.Default.Settings,
                    contentDescription = "Settings",
                    tint = MaterialTheme.colorScheme.primary
                )
            }
        }
        
        // Status Card
        Card(
            modifier = Modifier.fillMaxWidth(),
            shape = RoundedCornerShape(16.dp),
            colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
            elevation = CardDefaults.cardElevation(4.dp)
        ) {
            Column(
                modifier = Modifier.padding(24.dp),
                horizontalAlignment = Alignment.CenterHorizontally
            ) {
                Text(
                    text = connectionStatus,
                    fontSize = 20.sp,
                    fontWeight = FontWeight.Medium,
                    color = if (isConnected) Color(0xFF4CAF50) else MaterialTheme.colorScheme.onSurface
                )
                if (isConnected) {
                    Text(
                        text = "via $activeTransport",
                        fontSize = 14.sp,
                        color = Color.Gray
                    )
                }
            }
        }
        
        // Mode Controls
        Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(16.dp)) {
            Button(
                onClick = { ConnectionManager.enableWifiMode() },
                modifier = Modifier.weight(1f),
                colors = ButtonDefaults.buttonColors(
                    containerColor = if (activeTransport == ConnectionType.WIFI) MaterialTheme.colorScheme.primary else Color.Gray
                )
            ) { Text("Wi-Fi") }
            
            Button(
                onClick = { ConnectionManager.enableBluetoothMode() },
                modifier = Modifier.weight(1f),
                colors = ButtonDefaults.buttonColors(
                    containerColor = if (activeTransport == ConnectionType.BLUETOOTH) MaterialTheme.colorScheme.primary else Color.Gray
                )
            ) { Text("Bluetooth") }
        }

        if (isConnected) {
            Button(
                onClick = { ConnectionManager.disconnect() },
                modifier = Modifier.fillMaxWidth(),
                colors = ButtonDefaults.buttonColors(containerColor = Color(0xFFD32F2F))
            ) { Text("Disconnect") }
        }

        // --- Call Simulator UI ---
        Divider(modifier = Modifier.padding(vertical = 8.dp))
        Text("DEBUG: Call Simulator", style = MaterialTheme.typography.titleSmall)
        
        Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Button(
                onClick = { CallSimulator.simulateIncomingCall(context, "Tony Stark", "555-0199") },
                modifier = Modifier.weight(1f)
            ) { Text("Stark", fontSize = 12.sp) }
            
            Button(
                onClick = { CallSimulator.simulateIncomingCall(context, "Pepper Potts", "555-0123") },
                modifier = Modifier.weight(1f)
            ) { Text("Potts", fontSize = 12.sp) }
            
            Button(
                onClick = { CallSimulator.simulateIncomingCall(context, "Unknown", "Unknown") },
                modifier = Modifier.weight(1f)
            ) { Text("Unknown", fontSize = 12.sp) }
        }
    }
}
