package com.dynoip.app.data.repository

import com.dynoip.app.data.api.DynoIPApi
import com.dynoip.app.data.api.TokenManager
import com.dynoip.app.data.model.*
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class AuthRepository @Inject constructor(
    private val api: DynoIPApi,
    private val tokenManager: TokenManager
) {
    val isLoggedIn: Boolean get() = tokenManager.isLoggedIn

    suspend fun login(email: String, password: String): Result<TokenResponse> {
        return try {
            val resp = api.login(LoginRequest(email, password))
            if (resp.isSuccessful && resp.body() != null) {
                val body = resp.body()!!
                if (body.requiresTwoFactor != true) {
                    tokenManager.saveTokens(body.accessToken, body.refreshToken)
                }
                Result.success(body)
            } else {
                val msg = resp.errorBody()?.string() ?: "Login failed"
                Result.failure(Exception(msg))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun verifyTwoFactor(tempToken: String, code: String): Result<TokenResponse> {
        return try {
            val resp = api.login2fa(TwoFactorRequest(tempToken, code))
            if (resp.isSuccessful && resp.body() != null) {
                val body = resp.body()!!
                tokenManager.saveTokens(body.accessToken, body.refreshToken)
                Result.success(body)
            } else {
                val msg = resp.errorBody()?.string() ?: "2FA failed"
                Result.failure(Exception(msg))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun getMe(): Result<UserResponse> {
        return try {
            val resp = api.getMe()
            if (resp.isSuccessful && resp.body() != null) {
                Result.success(resp.body()!!)
            } else {
                Result.failure(Exception("Failed to fetch user"))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    fun logout() {
        tokenManager.clear()
    }
}
