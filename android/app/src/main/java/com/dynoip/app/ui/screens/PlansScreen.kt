package com.dynoip.app.ui.screens

import android.content.Intent
import android.net.Uri
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Check
import androidx.compose.material.icons.filled.Star
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.dynoip.app.data.model.MyPlanResponse
import com.dynoip.app.data.model.PlanInfo
import com.dynoip.app.data.repository.PlanRepository
import com.dynoip.app.ui.theme.*
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

data class PlansUiState(
    val isLoading: Boolean = true,
    val planData: MyPlanResponse? = null,
    val error: String? = null,
    val checkoutUrl: String? = null
)

@HiltViewModel
class PlansViewModel @Inject constructor(
    private val planRepository: PlanRepository
) : ViewModel() {
    private val _uiState = MutableStateFlow(PlansUiState())
    val uiState = _uiState.asStateFlow()

    init { load() }

    fun load() {
        viewModelScope.launch {
            _uiState.value = PlansUiState(isLoading = true)
            planRepository.getMyPlan().fold(
                onSuccess = { resp ->
                    _uiState.value = PlansUiState(isLoading = false, planData = resp)
                },
                onFailure = { e ->
                    _uiState.value = PlansUiState(isLoading = false, error = e.message)
                }
            )
        }
    }

    fun checkout(planName: String) {
        viewModelScope.launch {
            planRepository.createCheckout(planName).fold(
                onSuccess = { resp ->
                    _uiState.value = _uiState.value.copy(checkoutUrl = resp.url)
                },
                onFailure = { /* ignore */ }
            )
        }
    }

    fun clearCheckout() {
        _uiState.value = _uiState.value.copy(checkoutUrl = null)
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun PlansScreen(viewModel: PlansViewModel = hiltViewModel()) {
    val uiState by viewModel.uiState.collectAsState()
    val context = LocalContext.current

    // Open checkout URL in browser
    LaunchedEffect(uiState.checkoutUrl) {
        uiState.checkoutUrl?.let { url ->
            val intent = Intent(Intent.ACTION_VIEW, Uri.parse(url))
            context.startActivity(intent)
            viewModel.clearCheckout()
        }
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Plans") },
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
                uiState.planData != null -> {
                    val data = uiState.planData!!
                    LazyColumn(
                        contentPadding = PaddingValues(16.dp),
                        verticalArrangement = Arrangement.spacedBy(16.dp)
                    ) {
                        // Current plan
                        item {
                            Card(
                                shape = RoundedCornerShape(12.dp),
                                colors = CardDefaults.cardColors(containerColor = SurfaceVariant)
                            ) {
                                Column(
                                    modifier = Modifier.padding(16.dp).fillMaxWidth(),
                                    horizontalAlignment = Alignment.CenterHorizontally
                                ) {
                                    Text("Current Plan", style = MaterialTheme.typography.bodySmall)
                                    Text(
                                        data.plan,
                                        style = MaterialTheme.typography.headlineMedium,
                                        color = Accent,
                                        fontWeight = FontWeight.Bold
                                    )
                                    Text(
                                        "${data.subdomainCount} / ${data.subdomainLimit} subdomains used",
                                        style = MaterialTheme.typography.bodyMedium,
                                        color = TextSecondary
                                    )
                                }
                            }
                        }

                        // Current plan info
                        data.planInfo?.let { plan ->
                            item {
                                PlanCard(
                                    plan = plan,
                                    isCurrent = true,
                                    onSelect = {}
                                )
                            }
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun PlanCard(plan: PlanInfo, isCurrent: Boolean, onSelect: () -> Unit) {
    val borderColor = if (isCurrent) Accent else Border
    Card(
        shape = RoundedCornerShape(12.dp),
        colors = CardDefaults.cardColors(containerColor = SurfaceVariant),
        border = CardDefaults.outlinedCardBorder().takeIf { isCurrent }
    ) {
        Column(modifier = Modifier.padding(16.dp)) {
            Row(
                verticalAlignment = Alignment.CenterVertically,
                modifier = Modifier.fillMaxWidth()
            ) {
                Text(
                    plan.name,
                    style = MaterialTheme.typography.titleLarge,
                    fontWeight = FontWeight.Bold,
                    color = if (isCurrent) Accent else TextPrimary,
                    modifier = Modifier.weight(1f)
                )
                if (isCurrent) {
                    Icon(Icons.Default.Star, contentDescription = "Current", tint = Accent)
                }
            }

            Spacer(modifier = Modifier.height(4.dp))
            Text(
                text = if (plan.priceMonthly > 0) "$${String.format("%.2f", plan.priceMonthly)}/mo" else "Free",
                style = MaterialTheme.typography.titleMedium,
                color = Accent2,
                fontWeight = FontWeight.SemiBold
            )

            Spacer(modifier = Modifier.height(12.dp))

            // Features
            plan.features.forEach { feature ->
                Row(
                    verticalAlignment = Alignment.CenterVertically,
                    modifier = Modifier.padding(vertical = 2.dp)
                ) {
                    Icon(
                        Icons.Default.Check,
                        contentDescription = null,
                        tint = Success,
                        modifier = Modifier.size(16.dp)
                    )
                    Spacer(modifier = Modifier.width(8.dp))
                    Text(feature, style = MaterialTheme.typography.bodyMedium, color = TextSecondary)
                }
            }

            Spacer(modifier = Modifier.height(12.dp))

            if (isCurrent) {
                OutlinedButton(
                    onClick = {},
                    enabled = false,
                    modifier = Modifier.fillMaxWidth()
                ) {
                    Text("Current Plan")
                }
            } else {
                Button(
                    onClick = onSelect,
                    modifier = Modifier.fillMaxWidth(),
                    colors = ButtonDefaults.buttonColors(containerColor = Accent)
                ) {
                    Text(if (plan.price > 0) "Upgrade" else "Downgrade")
                }
            }
        }
    }
}
