#!/bin/bash
# =============================================================================
# Dyno-IP DDNS Update Client — Bash (Linux / macOS / WSL)
# =============================================================================
# Automatically updates your dynamic IP address with Dyno-IP.
#
# Setup:
#   1. Save this file: curl -O https://dyno-ip.com/clients/dynoip-update.sh
#   2. Make executable: chmod +x dynoip-update.sh
#   3. Edit the TOKEN below (from your Dyno-IP dashboard)
#   4. Run manually:   ./dynoip-update.sh
#   5. Or add a cron:  */5 * * * * /path/to/dynoip-update.sh >> /var/log/dynoip.log 2>&1
#
# Usage:
#   ./dynoip-update.sh                    # Auto-detect IP
#   ./dynoip-update.sh 203.0.113.50       # Set specific IP
#   DYNOIP_TOKEN=xxx ./dynoip-update.sh   # Token via env var
# =============================================================================

set -euo pipefail

# ── Configuration ──
# Set your update token here or via DYNOIP_TOKEN environment variable
TOKEN="${DYNOIP_TOKEN:-YOUR_UPDATE_TOKEN_HERE}"
API_URL="${DYNOIP_API_URL:-https://dyno-ip.com/api/ip/update}"

# ── Validate ──
if [ "$TOKEN" = "YOUR_UPDATE_TOKEN_HERE" ]; then
    echo "[ERROR] Please set your update token in the script or DYNOIP_TOKEN env var"
    exit 1
fi

# ── Determine IP ──
if [ $# -ge 1 ]; then
    IP="$1"
else
    IP="AUTO"
fi

# ── Update ──
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

# Try curl first, fall back to wget
if command -v curl &>/dev/null; then
    RESPONSE=$(curl -s -w "\n%{http_code}" \
        "${API_URL}?token=${TOKEN}&ip=${IP}" \
        --max-time 10 2>&1)
elif command -v wget &>/dev/null; then
    RESPONSE=$(wget -qO- --timeout=10 \
        "${API_URL}?token=${TOKEN}&ip=${IP}" 2>&1)
else
    echo "[$TIMESTAMP] ERROR: Neither curl nor wget found"
    exit 1
fi

# Parse response
HTTP_CODE=$(echo "$RESPONSE" | tail -1)
BODY=$(echo "$RESPONSE" | sed '$d')

if [ "$HTTP_CODE" = "200" ]; then
    SUBDOMAIN=$(echo "$BODY" | grep -o '"subdomain":"[^"]*"' | cut -d'"' -f4)
    NEW_IP=$(echo "$BODY" | grep -o '"new_ip":"[^"]*"' | cut -d'"' -f4)
    CHANGED=$(echo "$BODY" | grep -o '"changed":[a-z]*' | cut -d: -f2)

    if [ "$CHANGED" = "true" ]; then
        echo "[$TIMESTAMP] UPDATED: ${SUBDOMAIN}.dyno-ip.com → ${NEW_IP}"
    else
        echo "[$TIMESTAMP] OK: ${SUBDOMAIN}.dyno-ip.com = ${NEW_IP} (no change)"
    fi
elif [ "$HTTP_CODE" = "429" ]; then
    echo "[$TIMESTAMP] RATE LIMITED: Wait before retrying"
else
    echo "[$TIMESTAMP] ERROR (HTTP $HTTP_CODE): $BODY"
    exit 1
fi
