package com.dynoip.app.ui.navigation

import android.net.Uri
import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Dashboard
import androidx.compose.material.icons.filled.History
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material.icons.filled.ShoppingCart
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.navigation.NavHostController
import androidx.navigation.NavType
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.currentBackStackEntryAsState
import androidx.navigation.navArgument
import com.dynoip.app.ui.screens.*

sealed class Screen(val route: String, val label: String, val icon: ImageVector? = null) {
    data object Login : Screen("login", "Login")
    data object TwoFactor : Screen("two_factor/{tempToken}", "Two-Factor") {
        fun createRoute(tempToken: String) = "two_factor/$tempToken"
    }
    data object Dashboard : Screen("dashboard", "Dashboard", Icons.Default.Dashboard)
    data object SubdomainDetail : Screen("subdomain/{name}", "Detail") {
        fun createRoute(name: String) = "subdomain/$name"
    }
    data object CreateSubdomain : Screen("create_subdomain", "Create")
    data object Activity : Screen("activity", "Activity", Icons.Default.History)
    data object Plans : Screen("plans", "Plans", Icons.Default.ShoppingCart)
    data object Settings : Screen("settings", "Settings", Icons.Default.Settings)
}

val bottomBarScreens = listOf(Screen.Dashboard, Screen.Activity, Screen.Plans, Screen.Settings)

@Composable
fun DynoIPNavGraph(
    navController: NavHostController,
    isLoggedIn: Boolean,
    deepLinkUri: Uri?,
    modifier: Modifier = Modifier
) {
    val startDest = if (isLoggedIn) Screen.Dashboard.route else Screen.Login.route

    Scaffold(
        bottomBar = {
            val navBackStackEntry by navController.currentBackStackEntryAsState()
            val currentRoute = navBackStackEntry?.destination?.route
            val showBar = bottomBarScreens.any { it.route == currentRoute }
            if (showBar) {
                NavigationBar(
                    containerColor = MaterialTheme.colorScheme.surface
                ) {
                    bottomBarScreens.forEach { screen ->
                        NavigationBarItem(
                            icon = { Icon(screen.icon!!, contentDescription = screen.label) },
                            label = { Text(screen.label) },
                            selected = currentRoute == screen.route,
                            onClick = {
                                navController.navigate(screen.route) {
                                    popUpTo(Screen.Dashboard.route) { saveState = true }
                                    launchSingleTop = true
                                    restoreState = true
                                }
                            },
                            colors = NavigationBarItemDefaults.colors(
                                selectedIconColor = MaterialTheme.colorScheme.primary,
                                selectedTextColor = MaterialTheme.colorScheme.primary,
                                indicatorColor = MaterialTheme.colorScheme.surfaceVariant
                            )
                        )
                    }
                }
            }
        }
    ) { innerPadding ->
        NavHost(
            navController = navController,
            startDestination = startDest,
            modifier = modifier.padding(innerPadding)
        ) {
            composable(Screen.Login.route) {
                LoginScreen(
                    onLoginSuccess = {
                        navController.navigate(Screen.Dashboard.route) {
                            popUpTo(Screen.Login.route) { inclusive = true }
                        }
                    },
                    onTwoFactorRequired = { tempToken ->
                        navController.navigate(Screen.TwoFactor.createRoute(tempToken))
                    }
                )
            }
            composable(
                route = Screen.TwoFactor.route,
                arguments = listOf(navArgument("tempToken") { type = NavType.StringType })
            ) { backStackEntry ->
                val tempToken = backStackEntry.arguments?.getString("tempToken") ?: ""
                TwoFactorScreen(
                    tempToken = tempToken,
                    onVerified = {
                        navController.navigate(Screen.Dashboard.route) {
                            popUpTo(Screen.Login.route) { inclusive = true }
                        }
                    }
                )
            }
            composable(Screen.Dashboard.route) {
                DashboardScreen(
                    onSubdomainClick = { name ->
                        navController.navigate(Screen.SubdomainDetail.createRoute(name))
                    },
                    onCreateClick = {
                        navController.navigate(Screen.CreateSubdomain.route)
                    }
                )
            }
            composable(
                route = Screen.SubdomainDetail.route,
                arguments = listOf(navArgument("name") { type = NavType.StringType })
            ) { backStackEntry ->
                val name = backStackEntry.arguments?.getString("name") ?: ""
                SubdomainDetailScreen(
                    subdomainName = name,
                    onBack = { navController.popBackStack() }
                )
            }
            composable(Screen.CreateSubdomain.route) {
                CreateSubdomainScreen(
                    onCreated = { navController.popBackStack() },
                    onBack = { navController.popBackStack() }
                )
            }
            composable(Screen.Activity.route) {
                ActivityScreen()
            }
            composable(Screen.Plans.route) {
                PlansScreen()
            }
            composable(Screen.Settings.route) {
                SettingsScreen(
                    onLogout = {
                        navController.navigate(Screen.Login.route) {
                            popUpTo(0) { inclusive = true }
                        }
                    }
                )
            }
        }
    }
}
