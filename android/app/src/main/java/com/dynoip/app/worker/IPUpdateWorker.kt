package com.dynoip.app.worker

import android.content.Context
import android.util.Log
import androidx.hilt.work.HiltWorker
import androidx.work.CoroutineWorker
import androidx.work.WorkerParameters
import com.dynoip.app.data.api.DynoIPApi
import com.dynoip.app.data.api.TokenManager
import dagger.assisted.Assisted
import dagger.assisted.AssistedInject

@HiltWorker
class IPUpdateWorker @AssistedInject constructor(
    @Assisted context: Context,
    @Assisted params: WorkerParameters,
    private val api: DynoIPApi,
    private val tokenManager: TokenManager
) : CoroutineWorker(context, params) {

    override suspend fun doWork(): Result {
        if (!tokenManager.isLoggedIn) return Result.success()

        return try {
            val resp = api.listSubdomains()
            if (resp.isSuccessful && resp.body() != null) {
                val subdomains = resp.body()!!
                var allOk = true
                for (sub in subdomains) {
                    val parts = sub.fullHostname.split(".", limit = 2)
                    if (parts.size == 2) {
                        val refreshResp = api.refreshIP(parts[0], parts[1])
                        if (!refreshResp.isSuccessful) {
                            Log.w(TAG, "Failed to refresh ${sub.fullHostname}: ${refreshResp.code()}")
                            allOk = false
                        }
                    }
                }
                if (allOk) Result.success() else Result.retry()
            } else {
                Log.w(TAG, "Failed to list subdomains: ${resp.code()}")
                Result.retry()
            }
        } catch (e: Exception) {
            Log.e(TAG, "IP update failed", e)
            Result.retry()
        }
    }

    companion object {
        private const val TAG = "IPUpdateWorker"
    }
}
