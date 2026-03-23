package com.dynoip.app.data.api

import com.dynoip.app.data.model.RefreshRequest
import kotlinx.coroutines.runBlocking
import okhttp3.Interceptor
import okhttp3.Response
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class AuthInterceptor @Inject constructor(
    private val tokenManager: TokenManager
) : Interceptor {

    override fun intercept(chain: Interceptor.Chain): Response {
        val original = chain.request()
        val token = tokenManager.accessToken

        val request = if (token != null) {
            original.newBuilder()
                .header("Authorization", "Bearer $token")
                .build()
        } else {
            original
        }

        val response = chain.proceed(request)

        // Auto-refresh on 401
        if (response.code == 401 && tokenManager.refreshToken != null) {
            response.close()
            val refreshed = tryRefresh()
            if (refreshed) {
                val retryRequest = original.newBuilder()
                    .header("Authorization", "Bearer ${tokenManager.accessToken}")
                    .build()
                return chain.proceed(retryRequest)
            }
        }

        return response
    }

    @Synchronized
    private fun tryRefresh(): Boolean {
        val refresh = tokenManager.refreshToken ?: return false
        return try {
            runBlocking {
                val client = okhttp3.OkHttpClient()
                val moshi = com.squareup.moshi.Moshi.Builder()
                    .add(com.squareup.moshi.kotlin.reflect.KotlinJsonAdapterFactory())
                    .build()
                val api = retrofit2.Retrofit.Builder()
                    .baseUrl(com.dynoip.app.BuildConfig.API_BASE + "/")
                    .client(client)
                    .addConverterFactory(retrofit2.converter.moshi.MoshiConverterFactory.create(moshi))
                    .build()
                    .create(DynoIPApi::class.java)
                val resp = api.refreshToken(RefreshRequest(refresh))
                if (resp.isSuccessful && resp.body() != null) {
                    val body = resp.body()!!
                    tokenManager.saveTokens(body.accessToken, body.refreshToken)
                    true
                } else {
                    tokenManager.clear()
                    false
                }
            }
        } catch (_: Exception) {
            tokenManager.clear()
            false
        }
    }
}
