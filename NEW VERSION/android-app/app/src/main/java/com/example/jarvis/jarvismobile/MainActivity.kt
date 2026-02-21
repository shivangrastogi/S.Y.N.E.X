package com.example.jarvis.jarvismobile

import android.Manifest
import android.app.role.RoleManager
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.provider.Settings
import android.util.Log
import android.widget.Toast
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.*
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Call
import androidx.compose.material.icons.filled.Home
import androidx.compose.material.icons.filled.Notifications
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.core.content.ContextCompat
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import com.jarvis.mobile.network.ConnectionListener
import com.jarvis.mobile.network.ConnectionManager
import com.jarvis.mobile.network.ConnectionType
import com.jarvis.mobile.network.JarvisMobileService
import com.jarvis.mobile.network.SettingsManager

class MainActivity : ComponentActivity(), ConnectionListener {
    
    private val TAG = "MainActivity"
    
    // Shared State for Home Screen
    var connectionStatus by mutableStateOf("Disconnected")
    var isConnected by mutableStateOf(false)
    var activeTransport by mutableStateOf(ConnectionType.NONE)
    
    // Permission state
    private var missingPermissions = mutableStateListOf<String>()
    private var showPermissionPopup by mutableStateOf(false)
    private var showNotificationAccessDialog by mutableStateOf(false)

    /**
     * list of permissions that require runtime approval.
     */
    private val requiredPermissions: List<String>
        get() {
            val perms = mutableListOf(
                Manifest.permission.READ_PHONE_STATE,
                Manifest.permission.READ_CALL_LOG,
                Manifest.permission.READ_CONTACTS,
                Manifest.permission.ANSWER_PHONE_CALLS,
                Manifest.permission.READ_PHONE_NUMBERS,
                Manifest.permission.RECORD_AUDIO
            )
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
                perms.add(Manifest.permission.BLUETOOTH_CONNECT)
                perms.add(Manifest.permission.BLUETOOTH_SCAN)
            }
            return perms
        }

    private val permissionLauncher = registerForActivityResult(
        ActivityResultContracts.RequestMultiplePermissions()
    ) { results ->
        checkPermissions()
        val allGranted = results.all { it.value }
        if (allGranted && !SettingsManager.roleRequestAttempted) {
            requestDialerRole()
        } else if (!allGranted) {
            Toast.makeText(this, "Permissions required for full functionality", Toast.LENGTH_LONG).show()
        }
    }

    private val roleLauncher = registerForActivityResult(
        ActivityResultContracts.StartActivityForResult()
    ) { result ->
        SettingsManager.roleRequestAttempted = true // Mark as attempted regardless of result to avoid loops
        if (result.resultCode == android.app.Activity.RESULT_OK) {
            Log.d(TAG, "Dialer role granted")
            Toast.makeText(this, "Dialer Role Granted", Toast.LENGTH_SHORT).show()
        } else {
            Log.e(TAG, "Dialer role denied")
            Toast.makeText(this, "Dialer Role Denied. Call sync may be limited.", Toast.LENGTH_LONG).show()
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        
        ConnectionManager.setListener(this)
        
        // Final check on creation
        checkPermissions(autoRequestRole = true)
        
        if (!isNotificationServiceEnabled()) {
            showNotificationAccessDialog = true
        }
        
        startJarvisService()
        
        setContent {
            JarvisApp()
        }
    }

    private fun checkPermissions(autoRequestRole: Boolean = false) {
        val stillMissing = requiredPermissions.filter { perm ->
            ContextCompat.checkSelfPermission(this, perm) != PackageManager.PERMISSION_GRANTED
        }
        
        missingPermissions.clear()
        missingPermissions.addAll(stillMissing)
        
        // Only show popup if there are actually missing permissions
        showPermissionPopup = missingPermissions.isNotEmpty()
        
        // If everything is granted, and we haven't tried the role yet
        if (!showPermissionPopup && autoRequestRole && !SettingsManager.roleRequestAttempted) {
            requestDialerRole()
        }
    }

    private fun requestDialerRole() {
        if (SettingsManager.roleRequestAttempted) return // Safety check

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            val roleManager = getSystemService(RoleManager::class.java)
            if (roleManager != null && roleManager.isRoleAvailable(RoleManager.ROLE_DIALER)) {
                if (!roleManager.isRoleHeld(RoleManager.ROLE_DIALER)) {
                    Log.d(TAG, "Requesting Dialer role")
                    val intent = roleManager.createRequestRoleIntent(RoleManager.ROLE_DIALER)
                    roleLauncher.launch(intent)
                } else {
                    Log.d(TAG, "Dialer role already held")
                    SettingsManager.roleRequestAttempted = true // Already have it, no need to ask again
                }
            } else {
                SettingsManager.roleRequestAttempted = true // Role not available, don't keep trying
            }
        } else {
            SettingsManager.roleRequestAttempted = true // Not required below Q
        }
    }
    
    private fun startJarvisService() {
        val intent = Intent(this, JarvisMobileService::class.java)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            startForegroundService(intent)
        } else {
            startService(intent)
        }
    }

    @OptIn(ExperimentalMaterial3Api::class)
    @Composable
    fun JarvisApp() {
        val navController = rememberNavController()
        var selectedItem by remember { mutableIntStateOf(0) }
        val items = listOf("Home", "Notifications", "Calls")
        val icons = listOf(Icons.Default.Home, Icons.Default.Notifications, Icons.Default.Call)

        MaterialTheme(
            colorScheme = darkColorScheme(
                primary = Color(0xFF00BCD4),
                secondary = Color(0xFF0D47A1),
                background = Color(0xFF0A0E1A),
                surface = Color(0xFF151B2E),
            )
        ) {
            Scaffold(
                bottomBar = {
                    NavigationBar(containerColor = MaterialTheme.colorScheme.surface) {
                        items.forEachIndexed { index, item ->
                            NavigationBarItem(
                                icon = { Icon(icons[index], contentDescription = item) },
                                label = { Text(item) },
                                selected = selectedItem == index,
                                onClick = {
                                    selectedItem = index
                                    navController.navigate(item) {
                                        popUpTo(navController.graph.startDestinationId)
                                        launchSingleTop = true
                                    }
                                }
                            )
                        }
                    }
                }
            ) { padding ->
                Box(modifier = Modifier.padding(padding)) {
                    NavHost(
                        navController = navController,
                        startDestination = "Home"
                    ) {
                        composable("Home") { 
                            JarvisHomeScreen(
                                connectionStatus = connectionStatus,
                                isConnected = isConnected,
                                activeTransport = activeTransport,
                                onSettingsClick = { navController.navigate("Settings") }
                            ) 
                        }
                        composable("Notifications") { NotificationsScreen() }
                        composable("Calls") { CallsScreen() }
                        composable("Settings") { SettingsScreen(onBack = { navController.popBackStack() }) }
                    }

                    if (showPermissionPopup) {
                        PermissionRationalePopup()
                    }
                    
                    if (showNotificationAccessDialog) {
                        NotificationAccessRationale()
                    }
                }
            }
        }
    }

    @Composable
    fun PermissionRationalePopup() {
        AlertDialog(
            onDismissRequest = { /* Don't dismiss without action */ },
            title = { Text("Permissions Required") },
            text = {
                Column {
                    Text("JARVIS requires these permissions to function as your smart assistant:", fontWeight = FontWeight.Bold)
                    Spacer(modifier = Modifier.height(12.dp))
                    
                    val permissionTips = mapOf(
                        Manifest.permission.READ_PHONE_STATE to "Identify who is calling you.",
                        Manifest.permission.READ_CALL_LOG to "Sync your call history to desktop.",
                        Manifest.permission.READ_CONTACTS to "Show names instead of just numbers.",
                        Manifest.permission.ANSWER_PHONE_CALLS to "Allow JARVIS to help you pick up calls.",
                        Manifest.permission.READ_PHONE_NUMBERS to "Required by system for call identification.",
                        Manifest.permission.RECORD_AUDIO to "Enable voice commands and assistant talkback.",
                        Manifest.permission.BLUETOOTH_CONNECT to "Connect to JARVIS over Bluetooth.",
                        Manifest.permission.BLUETOOTH_SCAN to "Find your JARVIS device nearby."
                    )

                    missingPermissions.forEach { perm ->
                        val friendlyName = perm.substringAfterLast(".")
                            .replace("_", " ")
                            .lowercase()
                            .replaceFirstChar { it.uppercase() }
                        
                        Column(modifier = Modifier.padding(vertical = 4.dp)) {
                            Text("• $friendlyName", style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.primary)
                            Text(permissionTips[perm] ?: "", style = MaterialTheme.typography.bodySmall, color = Color.Gray)
                        }
                    }
                    Spacer(modifier = Modifier.height(8.dp))
                    Text("Please grant these to unlock JARVIS's full potential.")
                }
            },
            confirmButton = {
                Button(onClick = {
                    permissionLauncher.launch(missingPermissions.toTypedArray())
                }) {
                    Text("Grant")
                }
            },
            dismissButton = {
                TextButton(onClick = {
                    val intent = Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS).apply {
                        data = Uri.fromParts("package", packageName, null)
                    }
                    startActivity(intent)
                }) {
                    Text("Settings")
                }
            }
        )
    }

    @Composable
    fun NotificationAccessRationale() {
        AlertDialog(
            onDismissRequest = { showNotificationAccessDialog = false },
            title = { Text("Notification Access Required") },
            text = {
                Text("To see your messages and alerts on desktop, JARVIS needs 'Notification Access'. Please find 'JARVIS' in the next screen and turn the switch ON.")
            },
            confirmButton = {
                Button(onClick = {
                    showNotificationAccessDialog = false
                    startActivity(Intent("android.settings.ACTION_NOTIFICATION_LISTENER_SETTINGS"))
                }) {
                    Text("Go to Settings")
                }
            },
            dismissButton = {
                TextButton(onClick = { showNotificationAccessDialog = false }) {
                    Text("Maybe Later")
                }
            }
        )
    }

    private fun isNotificationServiceEnabled(): Boolean {
        val cn = android.content.ComponentName(this, com.jarvis.mobile.network.JarvisNotificationListener::class.java)
        val flat = Settings.Secure.getString(contentResolver, "enabled_notification_listeners")
        return flat != null && flat.contains(cn.flattenToString())
    }

    override fun onResume() {
        super.onResume()
        // verify permissions on return to app
        checkPermissions()
    }

    // --- Listeners ---
    override fun onConnected(type: ConnectionType) {
        runOnUiThread { 
            isConnected = true
            activeTransport = type
            connectionStatus = "Connected" 
        }
    }

    override fun onDisconnected() {
        runOnUiThread { 
            isConnected = false
            activeTransport = ConnectionType.NONE
            connectionStatus = "Disconnected" 
        }
    }

    override fun onError(error: String) {
        runOnUiThread { connectionStatus = "Error: $error" }
    }

    override fun onConnectionFailed(error: String) {
         runOnUiThread { connectionStatus = "Failed: $error" }
    }

    override fun onDiscoveryStarted() {
         runOnUiThread { connectionStatus = "Searching..." }
    }
    
    override fun onMessageReceived(message: String) {}
    override fun onDeviceFound(name: String, ip: String, port: Int, path: String) {}
}
