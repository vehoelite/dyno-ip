#!/usr/bin/env python3
"""
Dyno-IP DDNS Update Client — Python (cross-platform)

Automatically updates your dynamic IP address with Dyno-IP.
Works on Linux, macOS, Windows, and anywhere Python 3.7+ is available.

Setup:
    1. pip install requests  (or use urllib — no dependencies mode below)
    2. Set your token below or via DYNOIP_TOKEN environment variable
    3. Run:  python dynoip-update.py
    4. Cron:  */5 * * * * python3 /path/to/dynoip-update.py >> /var/log/dynoip.log

Usage:
    python dynoip-update.py                     # Auto-detect IP
    python dynoip-update.py 203.0.113.50        # Set specific IP
    python dynoip-update.py --daemon             # Run as daemon (every 5 min)
    python dynoip-update.py --daemon --interval 120  # Custom interval (seconds)
    DYNOIP_TOKEN=xxx python dynoip-update.py    # Token via env var
"""

import os
import sys
import json
import time
import logging
from datetime import datetime
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

# ── Configuration ──
TOKEN = os.environ.get("DYNOIP_TOKEN", "YOUR_UPDATE_TOKEN_HERE")
API_URL = os.environ.get("DYNOIP_API_URL", "https://dyno-ip.com/api/ip/update")

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("dynoip")


def update_ip(token: str, ip: str = "AUTO", api_url: str = API_URL) -> dict:
    """Send an IP update request to the Dyno-IP API."""
    url = f"{api_url}?token={token}&ip={ip}"
    req = Request(url, method="GET")
    req.add_header("User-Agent", "DynoIP-Client/1.0 (Python)")

    try:
        with urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
            return {"success": True, "status": resp.status, **data}
    except HTTPError as e:
        body = e.read().decode() if e.fp else ""
        try:
            detail = json.loads(body).get("detail", body)
        except (json.JSONDecodeError, AttributeError):
            detail = body
        return {"success": False, "status": e.code, "detail": detail}
    except URLError as e:
        return {"success": False, "status": 0, "detail": str(e.reason)}
    except Exception as e:
        return {"success": False, "status": 0, "detail": str(e)}


def run_once(token: str, ip: str = "AUTO"):
    """Perform a single update and log the result."""
    result = update_ip(token, ip)

    if result["success"]:
        subdomain = result.get("subdomain", "?")
        new_ip = result.get("new_ip", "?")
        changed = result.get("changed", False)

        if changed:
            log.info("UPDATED: %s.dyno-ip.com -> %s", subdomain, new_ip)
        else:
            log.info("OK: %s.dyno-ip.com = %s (no change)", subdomain, new_ip)
        return True
    else:
        status = result.get("status", 0)
        detail = result.get("detail", "Unknown error")

        if status == 429:
            log.warning("RATE LIMITED: Wait before retrying")
        else:
            log.error("ERROR (HTTP %s): %s", status, detail)
        return status == 429  # Don't exit on rate limit in daemon mode


def daemon_loop(token: str, interval: int = 300):
    """Run updates in a loop (daemon mode)."""
    log.info("Starting Dyno-IP daemon (interval: %ds)", interval)
    while True:
        try:
            run_once(token)
        except KeyboardInterrupt:
            log.info("Daemon stopped by user")
            break
        except Exception as e:
            log.error("Unexpected error: %s", e)
        time.sleep(interval)


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Dyno-IP DDNS Update Client")
    parser.add_argument("ip", nargs="?", default="AUTO", help="IP address (default: AUTO-detect)")
    parser.add_argument("--token", default=TOKEN, help="Update token")
    parser.add_argument("--daemon", action="store_true", help="Run as daemon")
    parser.add_argument("--interval", type=int, default=300, help="Update interval in seconds (daemon mode, default: 300)")
    parser.add_argument("--api-url", default=API_URL, help="API endpoint URL")
    args = parser.parse_args()

    global API_URL
    API_URL = args.api_url

    if args.token == "YOUR_UPDATE_TOKEN_HERE":
        log.error("Please set your update token via --token or DYNOIP_TOKEN env var")
        sys.exit(1)

    if args.daemon:
        daemon_loop(args.token, args.interval)
    else:
        success = run_once(args.token, args.ip)
        if not success:
            sys.exit(1)


if __name__ == "__main__":
    main()
