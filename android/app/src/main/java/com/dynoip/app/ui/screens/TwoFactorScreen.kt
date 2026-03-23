package com.dynoip.app.ui.screens

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalFocusManager
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.dynoip.app.data.repository.AuthRepository
import com.dynoip.app.ui.theme.Accent
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

data class TwoFactorUiState(
    val isLoading: Boolean = false,
    val error: String? = null
)

@HiltViewModel
class TwoFactorViewModel @Inject constructor(
    private val authRepository: AuthRepository
) : ViewModel() {
    private val _uiState = MutableStateFlow(TwoFactorUiState())
    val uiState = _uiState.asStateFlow()

    fun verify(tempToken: String, code: String, onSuccess: () -> Unit) {
        viewModelScope.launch {
            _uiState.value = TwoFactorUiState(isLoading = true)
            authRepository.verifyTwoFactor(tempToken, code).fold(
                onSuccess = {
                    _uiState.value = TwoFactorUiState()
                    onSuccess()
                },
                onFailure = { e ->
                    _uiState.value = TwoFactorUiState(error = e.message ?: "Verification failed")
                }
            )
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun TwoFactorScreen(
    tempToken: String,
    onVerified: () -> Unit,
    viewModel: TwoFactorViewModel = hiltViewModel()
) {
    val uiState by viewModel.uiState.collectAsState()
    var code by remember { mutableStateOf("") }
    val focusManager = LocalFocusManager.current

    Box(
        modifier = Modifier
            .fillMaxSize()
            .padding(24.dp),
        contentAlignment = Alignment.Center
    ) {
        Column(
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.spacedBy(16.dp),
            modifier = Modifier.widthIn(max = 400.dp)
        ) {
            Text(
                text = "Two-Factor Authentication",
                style = MaterialTheme.typography.headlineMedium,
                color = Accent
            )
            Text(
                text = "Enter the 6-digit code from your authenticator app",
                style = MaterialTheme.typography.bodyMedium,
                textAlign = TextAlign.Center
            )

            Spacer(modifier = Modifier.height(8.dp))

            OutlinedTextField(
                value = code,
                onValueChange = { if (it.length <= 6) code = it },
                label = { Text("Code") },
                singleLine = true,
                keyboardOptions = KeyboardOptions(
                    keyboardType = KeyboardType.Number,
                    imeAction = ImeAction.Done
                ),
                keyboardActions = KeyboardActions(
                    onDone = {
                        focusManager.clearFocus()
                        viewModel.verify(tempToken, code, onVerified)
                    }
                ),
                modifier = Modifier.fillMaxWidth(),
                colors = OutlinedTextFieldDefaults.colors(
                    focusedBorderColor = Accent,
                    cursorColor = Accent
                )
            )

            if (uiState.error != null) {
                Text(
                    text = uiState.error!!,
                    color = MaterialTheme.colorScheme.error,
                    style = MaterialTheme.typography.bodySmall,
                    textAlign = TextAlign.Center,
                    modifier = Modifier.fillMaxWidth()
                )
            }

            Button(
                onClick = { viewModel.verify(tempToken, code, onVerified) },
                enabled = !uiState.isLoading && code.length == 6,
                modifier = Modifier
                    .fillMaxWidth()
                    .height(50.dp),
                colors = ButtonDefaults.buttonColors(containerColor = Accent)
            ) {
                if (uiState.isLoading) {
                    CircularProgressIndicator(
                        modifier = Modifier.size(20.dp),
                        color = MaterialTheme.colorScheme.onPrimary,
                        strokeWidth = 2.dp
                    )
                } else {
                    Text("Verify")
                }
            }
        }
    }
}
