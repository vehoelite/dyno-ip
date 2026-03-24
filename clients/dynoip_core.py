"""
Dyno-IP DDNS Update Client — Core logic (shared by all platforms)

Zero external dependencies — uses only Python stdlib.
"""

import json
import os
import logging
import time
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

__version__ = "2.6.0"

log = logging.getLogger("dynoip")


def update_ip(token: str, ip: str = "AUTO", api_url: str = "https://dyno-ip.com/api/ip/update") -> dict:
    """Send an IP update request to the Dyno-IP API. Returns a result dict."""
    url = f"{api_url}?token={token}&ip={ip}"
    req = Request(url, method="GET")
    req.add_header("User-Agent", f"DynoIP-Client/{__version__}")

    try:
        with urlopen(req, timeout=15) as resp:
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


def run_once(token: str, ip: str = "AUTO", api_url: str = "https://dyno-ip.com/api/ip/update") -> bool:
    """Perform a single update and log the result. Returns True on success."""
    result = update_ip(token, ip, api_url)

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
            return True  # Not a fatal error
        else:
            log.error("ERROR (HTTP %s): %s", status, detail)
            return False


def daemon_loop(token: str, interval: int = 300, api_url: str = "https://dyno-ip.com/api/ip/update", stop_event=None):
    """
    Run updates in a loop.
    stop_event: threading.Event or similar — set to stop the loop.
    """
    log.info("Starting Dyno-IP updater (interval: %ds)", interval)
    while True:
        if stop_event and stop_event.is_set():
            log.info("Stop signal received, exiting")
            break
        try:
            run_once(token, api_url=api_url)
        except Exception as e:
            log.error("Unexpected error: %s", e)

        # Sleep in small increments so we can respond to stop signals
        for _ in range(interval):
            if stop_event and stop_event.is_set():
                break
            time.sleep(1)
