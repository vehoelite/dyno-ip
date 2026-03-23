package com.dynoip.app.data.repository

import com.dynoip.app.data.api.DynoIPApi
import com.dynoip.app.data.model.*
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class SubdomainRepository @Inject constructor(
    private val api: DynoIPApi
) {
    suspend fun getAvailableDomains(): Result<AvailableDomainsResponse> {
        return try {
            val resp = api.getAvailableDomains()
            if (resp.isSuccessful && resp.body() != null) {
                Result.success(resp.body()!!)
            } else {
                Result.failure(Exception("Failed to fetch domains"))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun listSubdomains(): Result<List<DynamicIPResponse>> {
        return try {
            val resp = api.listSubdomains()
            if (resp.isSuccessful && resp.body() != null) {
                Result.success(resp.body()!!)
            } else {
                Result.failure(Exception("Failed to list subdomains"))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun createSubdomain(subdomain: String, domain: String): Result<DynamicIPResponse> {
        return try {
            val resp = api.createSubdomain(CreateSubdomainRequest(subdomain, domain))
            if (resp.isSuccessful && resp.body() != null) {
                Result.success(resp.body()!!)
            } else {
                val msg = resp.errorBody()?.string() ?: "Failed to create"
                Result.failure(Exception(msg))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun deleteSubdomain(subdomain: String, domain: String): Result<Unit> {
        return try {
            val resp = api.deleteSubdomain(subdomain, domain)
            if (resp.isSuccessful) Result.success(Unit)
            else Result.failure(Exception("Failed to delete subdomain"))
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun refreshIP(subdomain: String, domain: String): Result<IPUpdateResponse> {
        return try {
            val resp = api.refreshIP(subdomain, domain)
            if (resp.isSuccessful && resp.body() != null) {
                Result.success(resp.body()!!)
            } else {
                Result.failure(Exception("Failed to refresh IP"))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun regenerateToken(subdomain: String, domain: String): Result<DynamicIPResponse> {
        return try {
            val resp = api.regenerateToken(subdomain, domain)
            if (resp.isSuccessful && resp.body() != null) {
                Result.success(resp.body()!!)
            } else {
                Result.failure(Exception("Failed to regenerate token"))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun getHistory(subdomain: String, domain: String): Result<IPHistoryResponse> {
        return try {
            val resp = api.getHistory(subdomain, domain)
            if (resp.isSuccessful && resp.body() != null) {
                Result.success(resp.body()!!)
            } else {
                Result.failure(Exception("Failed to fetch history"))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun getVisitors(subdomain: String, domain: String): Result<VisitorStatsResponse> {
        return try {
            val resp = api.getVisitors(subdomain, domain)
            if (resp.isSuccessful && resp.body() != null) {
                Result.success(resp.body()!!)
            } else {
                Result.failure(Exception("Failed to fetch visitors"))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun getActivity(): Result<ActivityFeedResponse> {
        return try {
            val resp = api.getActivity()
            if (resp.isSuccessful && resp.body() != null) {
                Result.success(resp.body()!!)
            } else {
                Result.failure(Exception("Failed to fetch activity"))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }
}
