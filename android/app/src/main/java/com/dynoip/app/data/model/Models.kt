package com.dynoip.app.data.model

import com.squareup.moshi.Json
import com.squareup.moshi.JsonClass

// ── Auth ──

@JsonClass(generateAdapter = true)
data class LoginRequest(
    val email: String,
    val password: String
)

@JsonClass(generateAdapter = true)
data class TokenResponse(
    @Json(name = "access_token") val accessToken: String = "",
    @Json(name = "refresh_token") val refreshToken: String = "",
    @Json(name = "token_type") val tokenType: String = "bearer",
    @Json(name = "requires_2fa") val requires2fa: Boolean = false,
    @Json(name = "challenge_token") val challengeToken: String? = null
)

@JsonClass(generateAdapter = true)
data class TwoFactorRequest(
    @Json(name = "challenge_token") val challengeToken: String,
    val code: String
)

@JsonClass(generateAdapter = true)
data class RefreshRequest(
    @Json(name = "refresh_token") val refreshToken: String
)

@JsonClass(generateAdapter = true)
data class UserResponse(
    val id: Int,
    val email: String,
    val username: String,
    val plan: String,
    @Json(name = "is_active") val isActive: Boolean,
    @Json(name = "is_admin") val isAdmin: Boolean = false,
    @Json(name = "totp_enabled") val totpEnabled: Boolean = false,
    @Json(name = "avatar_url") val avatarUrl: String? = null,
    @Json(name = "plan_expires_at") val planExpiresAt: String? = null,
    @Json(name = "created_at") val createdAt: String = ""
)

// ── Dynamic IP ──

@JsonClass(generateAdapter = true)
data class CreateSubdomainRequest(
    val subdomain: String,
    val domain: String? = null
)

@JsonClass(generateAdapter = true)
data class DynamicIPResponse(
    val id: Int,
    val subdomain: String,
    val domain: String,
    @Json(name = "full_hostname") val fullHostname: String,
    @Json(name = "current_ip") val currentIp: String?,
    @Json(name = "update_token") val updateToken: String,
    @Json(name = "is_active") val isActive: Boolean,
    @Json(name = "last_update") val lastUpdate: String?,
    @Json(name = "created_at") val createdAt: String
)

@JsonClass(generateAdapter = true)
data class AvailableDomainsResponse(
    val domains: List<String>,
    val default: String
)

@JsonClass(generateAdapter = true)
data class IPUpdateResponse(
    val subdomain: String,
    val domain: String,
    @Json(name = "full_hostname") val fullHostname: String,
    @Json(name = "old_ip") val oldIp: String?,
    @Json(name = "new_ip") val newIp: String,
    val changed: Boolean
)

@JsonClass(generateAdapter = true)
data class IPLogEntry(
    @Json(name = "old_ip") val oldIp: String?,
    @Json(name = "new_ip") val newIp: String,
    @Json(name = "source_ip") val sourceIp: String?,
    @Json(name = "created_at") val createdAt: String
)

@JsonClass(generateAdapter = true)
data class IPHistoryResponse(
    val subdomain: String,
    val entries: List<IPLogEntry>,
    val total: Int
)

// ── Visitors ──

@JsonClass(generateAdapter = true)
data class VisitorEntry(
    @Json(name = "visitor_ip") val visitorIp: String,
    @Json(name = "user_agent") val userAgent: String?,
    val referer: String?,
    val path: String,
    val country: String?,
    @Json(name = "created_at") val createdAt: String
)

@JsonClass(generateAdapter = true)
data class VisitorStatsResponse(
    val subdomain: String,
    @Json(name = "total_hits") val totalHits: Int,
    @Json(name = "unique_visitors") val uniqueVisitors: Int,
    val recent: List<VisitorEntry>
)

// ── Activity Feed ──

@JsonClass(generateAdapter = true)
data class ActivityEntry(
    val kind: String,
    val timestamp: String,
    val title: String,
    val detail: String?,
    @Json(name = "source_ip") val sourceIp: String?,
    val country: String?,
    val subdomain: String?
)

@JsonClass(generateAdapter = true)
data class ActivityFeedResponse(
    val events: List<ActivityEntry>,
    val total: Int
)

// ── Plans ──

@JsonClass(generateAdapter = true)
data class PlanInfo(
    val slug: String = "",
    val name: String = "",
    @Json(name = "price_monthly") val priceMonthly: Double = 0.0,
    val description: String = "",
    val features: List<String> = emptyList()
)

@JsonClass(generateAdapter = true)
data class MyPlanResponse(
    val plan: String = "",
    @Json(name = "plan_info") val planInfo: PlanInfo? = null,
    @Json(name = "subdomain_count") val subdomainCount: Int = 0,
    @Json(name = "subdomain_limit") val subdomainLimit: Int = 1
)

// ── Generic ──

@JsonClass(generateAdapter = true)
data class MessageResponse(
    val message: String,
    val detail: String? = null
)

@JsonClass(generateAdapter = true)
data class CheckoutResponse(
    val url: String
)

@JsonClass(generateAdapter = true)
data class CheckoutRequest(
    val plan: String
)
