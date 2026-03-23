# =============================================================================
# Dyno-IP DDNS Update Client — PowerShell (Windows)
# =============================================================================
# Automatically updates your dynamic IP address with Dyno-IP.
#
# Setup:
#   1. Save this file to a convenient location
#   2. Edit the $Token below (from your Dyno-IP dashboard)
#   3. Run manually:  .\dynoip-update.ps1
#   4. Or schedule via Task Scheduler (every 5 minutes)
#
# Usage:
#   .\dynoip-update.ps1                              # Auto-detect IP
#   .\dynoip-update.ps1 -IP 203.0.113.50             # Set specific IP
#   $env:DYNOIP_TOKEN = "xxx"; .\dynoip-update.ps1   # Token via env var
#
# Task Scheduler (one-liner to create scheduled task):
#   $action = New-ScheduledTaskAction -Execute "powershell.exe" `
#       -Argument "-NoProfile -ExecutionPolicy Bypass -File C:\path\to\dynoip-update.ps1"
#   $trigger = New-ScheduledTaskTrigger -RepetitionInterval (New-TimeSpan -Minutes 5) `
#       -RepetitionDuration (New-TimeSpan -Days 365) -At (Get-Date)
#   Register-ScheduledTask -TaskName "DynoIP-Update" -Action $action -Trigger $trigger `
#       -Description "Dyno-IP dynamic DNS updater" -RunLevel Highest
# =============================================================================

[CmdletBinding()]
param(
    [string]$IP = "AUTO",
    [string]$Token = ""
)

# ── Configuration ──
$DefaultToken = "YOUR_UPDATE_TOKEN_HERE"
$ApiUrl = if ($env:DYNOIP_API_URL) { $env:DYNOIP_API_URL } else { "https://dyno-ip.com/api/ip/update" }

# Resolve token: parameter > env var > default
if (-not $Token) {
    $Token = if ($env:DYNOIP_TOKEN) { $env:DYNOIP_TOKEN } else { $DefaultToken }
}

if ($Token -eq "YOUR_UPDATE_TOKEN_HERE") {
    Write-Error "Please set your update token in the script, -Token parameter, or DYNOIP_TOKEN env var"
    exit 1
}

# ── Update ──
$Timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"

try {
    $uri = "${ApiUrl}?token=${Token}&ip=${IP}"
    $response = Invoke-RestMethod -Uri $uri -Method Get -TimeoutSec 10 -ErrorAction Stop

    $subdomain = $response.subdomain
    $newIp = $response.new_ip
    $changed = $response.changed

    if ($changed) {
        Write-Output "[$Timestamp] UPDATED: ${subdomain}.dyno-ip.com -> ${newIp}"
    } else {
        Write-Output "[$Timestamp] OK: ${subdomain}.dyno-ip.com = ${newIp} (no change)"
    }
}
catch {
    $statusCode = $_.Exception.Response.StatusCode.value__
    if ($statusCode -eq 429) {
        Write-Warning "[$Timestamp] RATE LIMITED: Wait before retrying"
    }
    else {
        Write-Error "[$Timestamp] ERROR (HTTP ${statusCode}): $($_.Exception.Message)"
        exit 1
    }
}
