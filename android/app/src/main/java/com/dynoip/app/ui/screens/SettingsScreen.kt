package com.dynoip.app.ui.screens

import android.os.Build
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.Logout
import androidx.compose.material.icons.filled.Notifications
import androidx.compose.material.icons.filled.Update
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import androidx.work.*
import com.dynoip.app.data.repository.AuthRepository
import com.dynoip.app.ui.theme.*
import com.dynoip.app.worker.IPUpdateWorker
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import java.util.concurrent.TimeUnit
import javax.inject.Inject

data class SettingsUiState(
    val email: String = "",
    val autoUpdateEnabled: Boolean = false,
    val isLoading: Boolean = true
)

@HiltViewModel
class SettingsViewModel @Inject constructor(
    private val authRepository: AuthRepository
) : ViewModel() {
    private val _uiState = MutableStateFlow(SettingsUiState())
    val uiState = _uiState.asStateFlow()

    init { loadUser() }

    private fun loadUser() {
        viewModelScope.launch {
            authRepository.getMe().fold(
                onSuccess = { user ->
                    _uiState.value = _uiState.value.copy(
                        email = user.email,
                        isLoading = false
                    )
                },
                onFailure = {
                    _uiState.value = _uiState.value.copy(isLoading = false)
                }
            )
        }
    }

    fun setAutoUpdate(enabled: Boolean) {
        _uiState.value = _uiState.value.copy(autoUpdateEnabled = enabled)
    }

    fun logout() {
        authRepository.logout()
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SettingsScreen(
    onLogout: () -> Unit,
    viewModel: SettingsViewModel = hiltViewModel()
) {
    val uiState by viewModel.uiState.collectAsState()
    val context = LocalContext.current

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Settings") },
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = Surface,
                    titleContentColor = TextPrimary
                )
            )
        }
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp)
        ) {
            // Account card
            Card(
                shape = RoundedCornerShape(12.dp),
                colors = CardDefaults.cardColors(containerColor = SurfaceVariant)
            ) {
                Column(modifier = Modifier.padding(16.dp)) {
                    Text("Account", style = MaterialTheme.typography.titleMedium, color = TextPrimary)
                    Spacer(modifier = Modifier.height(8.dp))
                    if (uiState.isLoading) {
                        CircularProgressIndicator(modifier = Modifier.size(20.dp), color = Accent, strokeWidth = 2.dp)
                    } else {
                        Text(uiState.email, style = MaterialTheme.typography.bodyLarge, color = Accent)
                    }
                }
            }

            // Background updates card
            Card(
                shape = RoundedCornerShape(12.dp),
                colors = CardDefaults.cardColors(containerColor = SurfaceVariant)
            ) {
                Column(modifier = Modifier.padding(16.dp)) {
                    Row(
                        verticalAlignment = Alignment.CenterVertically,
                        modifier = Modifier.fillMaxWidth()
                    ) {
                        Icon(Icons.Default.Update, contentDescription = null, tint = Accent)
                        Spacer(modifier = Modifier.width(12.dp))
                        Column(modifier = Modifier.weight(1f)) {
                            Text("Auto IP Updates", style = MaterialTheme.typography.titleMedium, color = TextPrimary)
                            Text(
                                "Update your IP every 15 minutes in the background",
                                style = MaterialTheme.typography.bodySmall,
                                color = TextDim
                            )
                        }
                        Switch(
                            checked = uiState.autoUpdateEnabled,
                            onCheckedChange = { enabled ->
                                viewModel.setAutoUpdate(enabled)
                                val workManager = WorkManager.getInstance(context)
                                if (enabled) {
                                    val constraints = Constraints.Builder()
                                        .setRequiredNetworkType(NetworkType.CONNECTED)
                                        .build()
                                    val request = PeriodicWorkRequestBuilder<IPUpdateWorker>(
                                        15, TimeUnit.MINUTES
                                    ).setConstraints(constraints).build()
                                    workManager.enqueueUniquePeriodicWork(
                                        "ip_update",
                                        ExistingPeriodicWorkPolicy.UPDATE,
                                        request
                                    )
                                } else {
                                    workManager.cancelUniqueWork("ip_update")
                                }
                            },
                            colors = SwitchDefaults.colors(
                                checkedThumbColor = Accent,
                                checkedTrackColor = AccentDark
                            )
                        )
                    }
                }
            }

            // App info
            Card(
                shape = RoundedCornerShape(12.dp),
                colors = CardDefaults.cardColors(containerColor = SurfaceVariant)
            ) {
                Column(modifier = Modifier.padding(16.dp)) {
                    Text("About", style = MaterialTheme.typography.titleMedium, color = TextPrimary)
                    Spacer(modifier = Modifier.height(8.dp))
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween
                    ) {
                        Text("Version", style = MaterialTheme.typography.bodyMedium, color = TextSecondary)
                        Text("1.0.0", style = MaterialTheme.typography.bodyMedium, color = TextPrimary)
                    }
                    Spacer(modifier = Modifier.height(4.dp))
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween
                    ) {
                        Text("Build", style = MaterialTheme.typography.bodyMedium, color = TextSecondary)
                        Text("Android ${Build.VERSION.RELEASE}", style = MaterialTheme.typography.bodyMedium, color = TextPrimary)
                    }
                }
            }

            Spacer(modifier = Modifier.weight(1f))

            // Logout button
            OutlinedButton(
                onClick = {
                    viewModel.logout()
                    WorkManager.getInstance(context).cancelUniqueWork("ip_update")
                    onLogout()
                },
                modifier = Modifier.fillMaxWidth().height(50.dp),
                colors = ButtonDefaults.outlinedButtonColors(contentColor = Error)
            ) {
                Icon(Icons.AutoMirrored.Filled.Logout, contentDescription = null)
                Spacer(modifier = Modifier.width(8.dp))
                Text("Sign Out")
            }
        }
    }
}
