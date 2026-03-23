package com.dynoip.app.ui.screens

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.dynoip.app.data.repository.SubdomainRepository
import com.dynoip.app.ui.theme.*
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

data class CreateSubdomainUiState(
    val isLoading: Boolean = false,
    val availableDomains: List<String> = emptyList(),
    val domainsLoading: Boolean = true,
    val error: String? = null,
    val created: Boolean = false
)

@HiltViewModel
class CreateSubdomainViewModel @Inject constructor(
    private val subdomainRepository: SubdomainRepository
) : ViewModel() {
    private val _uiState = MutableStateFlow(CreateSubdomainUiState())
    val uiState = _uiState.asStateFlow()

    init { loadDomains() }

    private fun loadDomains() {
        viewModelScope.launch {
            subdomainRepository.getAvailableDomains().fold(
                onSuccess = { resp ->
                    _uiState.value = _uiState.value.copy(
                        domainsLoading = false,
                        availableDomains = resp.domains
                    )
                },
                onFailure = {
                    _uiState.value = _uiState.value.copy(
                        domainsLoading = false,
                        availableDomains = listOf("dyno-ip.com")
                    )
                }
            )
        }
    }

    fun create(subdomain: String, domain: String) {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isLoading = true, error = null)
            subdomainRepository.createSubdomain(subdomain, domain).fold(
                onSuccess = {
                    _uiState.value = _uiState.value.copy(isLoading = false, created = true)
                },
                onFailure = { e ->
                    _uiState.value = _uiState.value.copy(isLoading = false, error = e.message)
                }
            )
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun CreateSubdomainScreen(
    onCreated: () -> Unit,
    onBack: () -> Unit,
    viewModel: CreateSubdomainViewModel = hiltViewModel()
) {
    val uiState by viewModel.uiState.collectAsState()
    var subdomain by remember { mutableStateOf("") }
    var selectedDomain by remember { mutableStateOf("") }
    var expanded by remember { mutableStateOf(false) }

    // Set default domain once loaded
    LaunchedEffect(uiState.availableDomains) {
        if (selectedDomain.isEmpty() && uiState.availableDomains.isNotEmpty()) {
            selectedDomain = uiState.availableDomains.first()
        }
    }

    // Auto-navigate after create
    LaunchedEffect(uiState.created) {
        if (uiState.created) onCreated()
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Create Subdomain") },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Back")
                    }
                },
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
                .padding(24.dp),
            verticalArrangement = Arrangement.spacedBy(20.dp)
        ) {
            Card(
                shape = RoundedCornerShape(12.dp),
                colors = CardDefaults.cardColors(containerColor = SurfaceVariant)
            ) {
                Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(16.dp)) {
                    OutlinedTextField(
                        value = subdomain,
                        onValueChange = { subdomain = it.lowercase().replace(Regex("[^a-z0-9-]"), "") },
                        label = { Text("Subdomain") },
                        singleLine = true,
                        modifier = Modifier.fillMaxWidth(),
                        colors = OutlinedTextFieldDefaults.colors(
                            focusedBorderColor = Accent,
                            cursorColor = Accent
                        )
                    )

                    // Domain dropdown
                    ExposedDropdownMenuBox(
                        expanded = expanded,
                        onExpandedChange = { expanded = !expanded }
                    ) {
                        OutlinedTextField(
                            value = selectedDomain,
                            onValueChange = {},
                            readOnly = true,
                            label = { Text("Domain") },
                            trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(expanded) },
                            modifier = Modifier.menuAnchor().fillMaxWidth(),
                            colors = OutlinedTextFieldDefaults.colors(
                                focusedBorderColor = Accent,
                                cursorColor = Accent
                            )
                        )
                        ExposedDropdownMenu(
                            expanded = expanded,
                            onDismissRequest = { expanded = false }
                        ) {
                            uiState.availableDomains.forEach { domain ->
                                DropdownMenuItem(
                                    text = { Text(domain) },
                                    onClick = {
                                        selectedDomain = domain
                                        expanded = false
                                    }
                                )
                            }
                        }
                    }

                    // Preview
                    if (subdomain.isNotBlank()) {
                        Text(
                            text = "$subdomain.$selectedDomain",
                            style = MaterialTheme.typography.titleMedium,
                            color = Accent
                        )
                    }
                }
            }

            if (uiState.error != null) {
                Text(uiState.error!!, color = Error, style = MaterialTheme.typography.bodySmall)
            }

            Button(
                onClick = { viewModel.create(subdomain, selectedDomain) },
                enabled = !uiState.isLoading && subdomain.isNotBlank() && selectedDomain.isNotBlank(),
                modifier = Modifier.fillMaxWidth().height(50.dp),
                colors = ButtonDefaults.buttonColors(containerColor = Accent)
            ) {
                if (uiState.isLoading) {
                    CircularProgressIndicator(
                        modifier = Modifier.size(20.dp),
                        color = Background,
                        strokeWidth = 2.dp
                    )
                } else {
                    Text("Create Subdomain")
                }
            }
        }
    }
}
