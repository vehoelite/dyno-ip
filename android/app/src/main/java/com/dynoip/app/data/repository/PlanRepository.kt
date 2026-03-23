package com.dynoip.app.data.repository

import com.dynoip.app.data.api.DynoIPApi
import com.dynoip.app.data.model.*
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class PlanRepository @Inject constructor(
    private val api: DynoIPApi
) {
    suspend fun getMyPlan(): Result<MyPlanResponse> {
        return try {
            val resp = api.getMyPlan()
            if (resp.isSuccessful && resp.body() != null) {
                Result.success(resp.body()!!)
            } else {
                Result.failure(Exception("Failed to fetch plan"))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun createCheckout(planName: String): Result<CheckoutResponse> {
        return try {
            val resp = api.createCheckout(CheckoutRequest(planName))
            if (resp.isSuccessful && resp.body() != null) {
                Result.success(resp.body()!!)
            } else {
                val msg = resp.errorBody()?.string() ?: "Checkout failed"
                Result.failure(Exception(msg))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }
}
