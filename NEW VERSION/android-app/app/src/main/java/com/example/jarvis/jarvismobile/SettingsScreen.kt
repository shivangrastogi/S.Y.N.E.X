package com.example.jarvis.jarvismobile

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
import com.jarvis.mobile.network.NotificationRepository
import com.jarvis.mobile.network.SettingsManager

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SettingsScreen(onBack: () -> Unit) {
    var notificationsEnabled by remember { mutableStateOf(SettingsManager.notificationsEnabled) }
    var autoConnectEnabled by remember { mutableStateOf(SettingsManager.autoConnectEnabled) }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Settings") },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.Default.ArrowBack, contentDescription = "Back")
                    }
                }
            )
        }
    ) { padding ->
        Column(
            modifier = Modifier
                .padding(padding)
                .fillMaxSize()
                .padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp)
        ) {
            // Notifications Toggle
            SettingsToggle(
                title = "Enable Notifications",
                subtitle = "Receive mobile notifications on your desktop",
                checked = notificationsEnabled,
                onCheckedChange = {
                    notificationsEnabled = it
                    SettingsManager.notificationsEnabled = it
                }
            )

            Divider()

            // Auto-connect Toggle
            SettingsToggle(
                title = "Auto-connect",
                subtitle = "Automatically connect to last used transport on startup",
                checked = autoConnectEnabled,
                onCheckedChange = {
                    autoConnectEnabled = it
                    SettingsManager.autoConnectEnabled = it
                }
            )

            Divider()

            // Clear Cache
            Button(
                onClick = { NotificationRepository.clear() },
                modifier = Modifier.fillMaxWidth(),
                colors = ButtonDefaults.buttonColors(containerColor = MaterialTheme.colorScheme.errorContainer, contentColor = MaterialTheme.colorScheme.error)
            ) {
                Text("Clear Notification History")
            }
            
            Spacer(modifier = Modifier.weight(1f))
            
            Text(
                text = "JARVIS Mobile v2.1",
                style = MaterialTheme.typography.labelSmall,
                color = Color.Gray,
                modifier = Modifier.align(Alignment.CenterHorizontally)
            )
        }
    }
}

@Composable
fun SettingsToggle(title: String, subtitle: String, checked: Boolean, onCheckedChange: (Boolean) -> Unit) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically
    ) {
        Column(modifier = Modifier.weight(1f)) {
            Text(text = title, style = MaterialTheme.typography.titleMedium)
            Text(text = subtitle, style = MaterialTheme.typography.bodySmall, color = Color.Gray)
        }
        Switch(checked = checked, onCheckedChange = onCheckedChange)
    }
}
