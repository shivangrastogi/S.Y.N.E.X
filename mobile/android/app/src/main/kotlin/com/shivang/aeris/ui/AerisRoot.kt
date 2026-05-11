package com.shivang.aeris.ui

import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.Chat
import androidx.compose.material.icons.outlined.GridView
import androidx.compose.material.icons.outlined.Settings
import androidx.compose.material.icons.outlined.Visibility
import androidx.compose.material3.Icon
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.navigation.NavDestination.Companion.hierarchy
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.currentBackStackEntryAsState
import androidx.navigation.compose.rememberNavController
import com.shivang.aeris.ui.chat.ChatScreen
import com.shivang.aeris.ui.settings.SettingsScreen
import com.shivang.aeris.ui.vision.VisionScreen
import com.shivang.aeris.ui.workbook.WorkbookScreen

private sealed class Tab(val route: String, val label: String, val icon: ImageVector) {
    data object Chat : Tab("chat", "Chat", Icons.Outlined.Chat)
    data object Workbook : Tab("workbook", "Workbook", Icons.Outlined.GridView)
    data object Vision : Tab("vision", "Vision", Icons.Outlined.Visibility)
    data object Settings : Tab("settings", "Settings", Icons.Outlined.Settings)
}

private val tabs = listOf(Tab.Chat, Tab.Workbook, Tab.Vision, Tab.Settings)

@Composable
fun AerisRoot() {
    val nav = rememberNavController()
    val backStack by nav.currentBackStackEntryAsState()
    val currentRoute = backStack?.destination?.route

    Scaffold(
        bottomBar = {
            NavigationBar {
                tabs.forEach { tab ->
                    val selected = backStack?.destination?.hierarchy?.any { it.route == tab.route } == true
                    NavigationBarItem(
                        selected = selected,
                        onClick = {
                            if (currentRoute != tab.route) {
                                nav.navigate(tab.route) {
                                    popUpTo(nav.graph.startDestinationId) { saveState = true }
                                    launchSingleTop = true
                                    restoreState = true
                                }
                            }
                        },
                        icon = { Icon(tab.icon, contentDescription = tab.label) },
                        label = { Text(tab.label) },
                    )
                }
            }
        }
    ) { padding ->
        NavHost(
            navController = nav,
            startDestination = Tab.Chat.route,
            modifier = Modifier.padding(padding),
        ) {
            composable(Tab.Chat.route) {
                ChatScreen(onSwitchToVision = { nav.navigate(Tab.Vision.route) })
            }
            composable(Tab.Workbook.route) { WorkbookScreen() }
            composable(Tab.Vision.route) { VisionScreen() }
            composable(Tab.Settings.route) { SettingsScreen() }
        }
    }
}
