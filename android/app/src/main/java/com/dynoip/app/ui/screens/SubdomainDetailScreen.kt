package com.dynoip.app.ui.screens

import android.widget.Toast
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.ContentCopy
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalClipboardManager
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.SavedStateHandle
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.dynoip.app.data.model.DynamicIPResponse
import com.dynoip.app.data.model.IPLogEntry
import com.dynoip.app.data.repository.SubdomainRepository
import com.dynoip.app.ui.theme.*
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

data class DetailUiState(
    val isLoading: Boolean = true,
    val subdomain: DynamicIPResponse? = null,
    val history: List<IPLogEntry> = emptyList(),
    val error: String? = null,
    val refreshing: Boolean = false,
    val showDeleteDialog: Boolean = false,
    val deleted: Boolean = false
)

@HiltViewModel
class SubdomainDetailViewModel @Inject constructor(
    private val subdomainRepository: SubdomainRepository,
    savedStateHandle: SavedStateHandle
) : ViewModel() {
    private val fullHostname: String = savedStateHandle["name"] ?: ""
    private val subdomain: String = fullHostname.substringBefore(".")
    private val domain: String = fullHostname.substringAfter(".")

    private val _uiState = MutableStateFlow(DetailUiState())
    val uiState = _uiState.asStateFlow()

    init { load() }

    fun load() {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isLoading = true, error = null)
            // Load subdomain list and find this one
            subdomainRepository.listSubdomains().fold(
                onSuccess = { list ->
                    val found = list.find { it.fullHostname == fullHostname }
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        subdomain = found,
                        error = if (found == null) "Subdomain not found" else null
                    )
                },
                onFailure = { e ->
                    _uiState.value = _uiState.value.copy(isLoading = false, error = e.message)
                }
            )
            // Load history
            subdomainRepository.getHistory(subdomain, domain).fold(
                onSuccess = { hist ->
                    _uiState.value = _uiState.value.copy(history = hist.entries)
                },
                onFailure = { /* ignore history errors */ }
            )
        }
    }

    fun refreshIP() {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(refreshing = true)
            subdomainRepository.refreshIP(subdomain, domain).fold(
                onSuccess = { load() },
                onFailure = { e ->
                    _uiState.value = _uiState.value.copy(refreshing = false, error = e.message)
                }
            )
        }
    }

    fun regenerateToken() {
        viewModelScope.launch {
            subdomainRepository.regenerateToken(subdomain, domain).fold(
                onSuccess = { updated ->
                    _uiState.value = _uiState.value.copy(subdomain = updated)
                },
                onFailure = { /* ignore */ }
            )
        }
    }

    fun showDeleteDialog() {
        _uiState.value = _uiState.value.copy(showDeleteDialog = true)
    }

    fun dismissDeleteDialog() {
        _uiState.value = _uiState.value.copy(showDeleteDialog = false)
    }

    fun delete() {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(showDeleteDialog = false)
            subdomainRepository.deleteSubdomain(subdomain, domain).fold(
                onSuccess = { _uiState.value = _uiState.value.copy(deleted = true) },
                onFailure = { e ->
                    _uiState.value = _uiState.value.copy(error = e.message)
                }
            )
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SubdomainDetailScreen(
    subdomainName: String,
    onBack: () -> Unit,
    viewModel: SubdomainDetailViewModel = hiltViewModel()
) {
    val uiState by viewModel.uiState.collectAsState()
    val clipboardManager = LocalClipboardManager.current
    val context = LocalContext.current

    // Auto-navigate back after delete
    LaunchedEffect(uiState.deleted) {
        if (uiState.deleted) onBack()
    }

    // Delete confirmation dialog
    if (uiState.showDeleteDialog) {
        AlertDialog(
            onDismissRequest = { viewModel.dismissDeleteDialog() },
            title = { Text("Delete Subdomain") },
            text = { Text("Are you sure you want to delete $subdomainName? This action cannot be undone.") },
            confirmButton = {
                TextButton(onClick = { viewModel.delete() }) {
                    Text("Delete", color = Error)
                }
            },
            dismissButton = {
                TextButton(onClick = { viewModel.dismissDeleteDialog() }) {
                    Text("Cancel")
                }
            },
            containerColor = SurfaceVariant
        )
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text(subdomainName) },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Back")
                    }
                },
                actions = {
                    IconButton(onClick = { viewModel.showDeleteDialog() }) {
                        Icon(Icons.Default.Delete, contentDescription = "Delete", tint = Error)
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = Surface,
                    titleContentColor = TextPrimary
                )
            )
        }
    ) { padding ->
        if (uiState.isLoading) {
            Box(modifier = Modifier.fillMaxSize().padding(padding), contentAlignment = Alignment.Center) {
                CircularProgressIndicator(color = Accent)
            }
            return@Scaffold
        }

        val sub = uiState.subdomain
        if (sub == null) {
            Box(modifier = Modifier.fillMaxSize().padding(padding), contentAlignment = Alignment.Center) {
                Text(uiState.error ?: "Not found", color = Error)
            }
            return@Scaffold
        }

        LazyColumn(
            modifier = Modifier.fillMaxSize().padding(padding),
            contentPadding = PaddingValues(16.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp)
        ) {
            // IP Info Card
            item {
                Card(
                    shape = RoundedCornerShape(12.dp),
                    colors = CardDefaults.cardColors(containerColor = SurfaceVariant)
                ) {
                    Column(modifier = Modifier.padding(16.dp)) {
                        Text("Current IP", style = MaterialTheme.typography.bodySmall)
                        Text(
                            sub.currentIp ?: "Not set",
                            style = MaterialTheme.typography.headlineMedium,
                            color = Accent
                        )
                        Spacer(modifier = Modifier.height(8.dp))
                        Text("Last Updated: ${sub.lastUpdate ?: "Never"}",
                            style = MaterialTheme.typography.bodySmall)

                        Spacer(modifier = Modifier.height(12.dp))
                        Button(
                            onClick = { viewModel.refreshIP() },
                            enabled = !uiState.refreshing,
                            colors = ButtonDefaults.buttonColors(containerColor = Accent)
                        ) {
                            Icon(Icons.Default.Refresh, contentDescription = null, modifier = Modifier.size(18.dp))
                            Spacer(modifier = Modifier.width(8.dp))
                            Text(if (uiState.refreshing) "Refreshing..." else "Refresh IP Now")
                        }
                    }
                }
            }

            // Update Token Card
            item {
                Card(
                    shape = RoundedCornerShape(12.dp),
                    colors = CardDefaults.cardColors(containerColor = SurfaceVariant)
                ) {
                    Column(modifier = Modifier.padding(16.dp)) {
                        Text("Update Token", style = MaterialTheme.typography.titleMedium)
                        Spacer(modifier = Modifier.height(8.dp))
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Text(
                                text = sub.updateToken ?: "—",
                                style = MaterialTheme.typography.bodyMedium.copy(
                                    fontFamily = FontFamily.Monospace
                                ),
                                color = TextSecondary,
                                modifier = Modifier.weight(1f)
                            )
                            IconButton(onClick = {
                                sub.updateToken?.let {
                                    clipboardManager.setText(AnnotatedString(it))
                                    Toast.makeText(context, "Copied!", Toast.LENGTH_SHORT).show()
                                }
                            }) {
                                Icon(Icons.Default.ContentCopy, contentDescription = "Copy", tint = Accent)
                            }
                        }
                        Spacer(modifier = Modifier.height(8.dp))
                        OutlinedButton(
                            onClick = { viewModel.regenerateToken() },
                            colors = ButtonDefaults.outlinedButtonColors(contentColor = Accent2)
                        ) {
                            Text("Regenerate Token")
                        }
                    }
                }
            }

            // IP History
            if (uiState.history.isNotEmpty()) {
                item {
                    Text("IP History", style = MaterialTheme.typography.titleMedium, color = TextPrimary)
                }
                items(uiState.history) { entry ->
                    Card(
                        shape = RoundedCornerShape(8.dp),
                        colors = CardDefaults.cardColors(containerColor = Surface)
                    ) {
                        Row(
                            modifier = Modifier.fillMaxWidth().padding(12.dp),
                            horizontalArrangement = Arrangement.SpaceBetween
                        ) {
                            Text(entry.ip, style = MaterialTheme.typography.bodyLarge, color = TextPrimary)
                            Text(entry.changedAt, style = MaterialTheme.typography.bodySmall, color = TextDim)
                        }
                    }
                }
            }
        }
    }
}
