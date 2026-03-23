package com.dynoip.app.ui.screens

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Circle
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.dynoip.app.data.model.ActivityEntry
import com.dynoip.app.data.repository.SubdomainRepository
import com.dynoip.app.ui.theme.*
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

data class ActivityUiState(
    val isLoading: Boolean = true,
    val entries: List<ActivityEntry> = emptyList(),
    val error: String? = null
)

@HiltViewModel
class ActivityViewModel @Inject constructor(
    private val subdomainRepository: SubdomainRepository
) : ViewModel() {
    private val _uiState = MutableStateFlow(ActivityUiState())
    val uiState = _uiState.asStateFlow()

    init { load() }

    fun load() {
        viewModelScope.launch {
            _uiState.value = ActivityUiState(isLoading = true)
            subdomainRepository.getActivity().fold(
                onSuccess = { resp ->
                    _uiState.value = ActivityUiState(isLoading = false, entries = resp.events)
                },
                onFailure = { e ->
                    _uiState.value = ActivityUiState(isLoading = false, error = e.message)
                }
            )
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ActivityScreen(viewModel: ActivityViewModel = hiltViewModel()) {
    val uiState by viewModel.uiState.collectAsState()

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Activity") },
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = Surface,
                    titleContentColor = TextPrimary
                )
            )
        }
    ) { padding ->
        Box(modifier = Modifier.fillMaxSize().padding(padding)) {
            when {
                uiState.isLoading -> {
                    CircularProgressIndicator(
                        modifier = Modifier.align(Alignment.Center),
                        color = Accent
                    )
                }
                uiState.error != null -> {
                    Column(
                        modifier = Modifier.align(Alignment.Center).padding(24.dp),
                        horizontalAlignment = Alignment.CenterHorizontally
                    ) {
                        Text(uiState.error!!, color = Error)
                        Spacer(modifier = Modifier.height(8.dp))
                        TextButton(onClick = { viewModel.load() }) {
                            Text("Retry", color = Accent)
                        }
                    }
                }
                uiState.entries.isEmpty() -> {
                    Text(
                        "No activity yet",
                        modifier = Modifier.align(Alignment.Center),
                        style = MaterialTheme.typography.bodyMedium,
                        color = TextDim
                    )
                }
                else -> {
                    LazyColumn(
                        contentPadding = PaddingValues(16.dp),
                        verticalArrangement = Arrangement.spacedBy(8.dp)
                    ) {
                        items(uiState.entries) { entry ->
                            ActivityCard(entry)
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun ActivityCard(entry: ActivityEntry) {
    val color = when {
        entry.kind.contains("create", ignoreCase = true) -> Success
        entry.kind.contains("delete", ignoreCase = true) -> Error
        entry.kind.contains("update", ignoreCase = true) -> Accent
        else -> TextSecondary
    }

    Card(
        shape = RoundedCornerShape(8.dp),
        colors = CardDefaults.cardColors(containerColor = SurfaceVariant)
    ) {
        Row(
            modifier = Modifier.fillMaxWidth().padding(12.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Icon(
                Icons.Default.Circle,
                contentDescription = null,
                tint = color,
                modifier = Modifier.size(8.dp)
            )
            Spacer(modifier = Modifier.width(12.dp))
            Column(modifier = Modifier.weight(1f)) {
                Text(entry.title, style = MaterialTheme.typography.bodyLarge, color = TextPrimary)
                if (entry.detail != null) {
                    Text(entry.detail, style = MaterialTheme.typography.bodySmall, color = TextDim)
                }
            }
            Text(entry.timestamp, style = MaterialTheme.typography.bodySmall, color = TextDim)
        }
    }
}
