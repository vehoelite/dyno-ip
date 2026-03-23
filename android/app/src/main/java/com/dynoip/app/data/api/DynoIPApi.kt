package com.dynoip.app.data.api

import com.dynoip.app.data.model.*
import retrofit2.Response
import retrofit2.http.*

interface DynoIPApi {

    // ── Auth ──

    @POST("auth/login")
    suspend fun login(@Body request: LoginRequest): Response<TokenResponse>

    @POST("auth/login/2fa")
    suspend fun login2fa(@Body request: TwoFactorRequest): Response<TokenResponse>

    @POST("auth/refresh")
    suspend fun refreshToken(@Body request: RefreshRequest): Response<TokenResponse>

    @GET("auth/me")
    suspend fun getMe(): Response<UserResponse>

    // ── Dynamic IP ──

    @GET("ip/domains")
    suspend fun getAvailableDomains(): Response<AvailableDomainsResponse>

    @POST("ip/create")
    suspend fun createSubdomain(@Body request: CreateSubdomainRequest): Response<DynamicIPResponse>

    @GET("ip/list")
    suspend fun listSubdomains(): Response<List<DynamicIPResponse>>

    @DELETE("ip/{subdomain}")
    suspend fun deleteSubdomain(@Path("subdomain") subdomain: String): Response<MessageResponse>

    @POST("ip/refresh/{subdomain}")
    suspend fun refreshIP(@Path("subdomain") subdomain: String): Response<IPUpdateResponse>

    @POST("ip/{subdomain}/regenerate-token")
    suspend fun regenerateToken(@Path("subdomain") subdomain: String): Response<DynamicIPResponse>

    @GET("ip/history/{subdomain}")
    suspend fun getHistory(
        @Path("subdomain") subdomain: String,
        @Query("limit") limit: Int = 50
    ): Response<IPHistoryResponse>

    @GET("ip/visitors/{subdomain}")
    suspend fun getVisitors(@Path("subdomain") subdomain: String): Response<VisitorStatsResponse>

    @GET("ip/activity")
    suspend fun getActivity(@Query("limit") limit: Int = 50): Response<ActivityFeedResponse>

    // ── Plans ──

    @GET("plans/my")
    suspend fun getMyPlan(): Response<MyPlanResponse>

    @POST("billing/checkout")
    suspend fun createCheckout(@Body request: CheckoutRequest): Response<CheckoutResponse>
}
