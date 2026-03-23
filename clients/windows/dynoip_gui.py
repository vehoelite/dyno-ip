"""
Dyno-IP Desktop v2.1 — Full GUI Client for Windows

Features:
  • JWT login / logout
  • System tray — minimize & close go to tray, right-click menu
  • Subdomain list with current IP, domain, last update
  • Create / delete subdomains (with domain picker)
  • One-click manual IP refresh per subdomain
  • Traffic / visitor stats per subdomain
  • Live activity log (IP change history)
  • Plans tab showing current tier + upgrade options
  • Background auto-refresh every 5 min

Build:
  pip install customtkinter requests Pillow pystray pyinstaller
  pyinstaller --onefile --windowed --name DynoIP ^
      --hidden-import customtkinter ^
      --hidden-import pystray._win32 ^
      --collect-data customtkinter ^
      dynoip_gui.py
"""

import json
import os
import subprocess
import sys
import threading
import time
import logging
import webbrowser
import winreg
from datetime import datetime, timezone
from urllib.parse import urlparse, parse_qs
from urllib.request import Request, urlopen
from urllib.error import URLError

import customtkinter as ctk
import requests

# pystray + Pillow for system tray
from PIL import Image, ImageDraw
import pystray

# ═══════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════

APP_NAME = "Dyno-IP"
APP_VERSION = "2.5.0"
API_BASE = "https://dyno-ip.com/api"
CONFIG_DIR = os.path.join(os.environ.get("APPDATA", "."), "DynoIP")
TOKEN_FILE = os.path.join(CONFIG_DIR, "session.json")
AUTO_REFRESH_INTERVAL = 300  # seconds

# Cyberpunk colour palette
C_BG        = "#0a0a12"
C_BG_CARD   = "#12121f"
C_BG_DARKER = "#080810"
C_ACCENT    = "#00e5ff"
C_ACCENT2   = "#7c4dff"
C_SUCCESS   = "#00e676"
C_ERROR     = "#ff1744"
C_WARNING   = "#ffab40"
C_TEXT       = "#e0e0e0"
C_TEXT_DIM   = "#6a6a8a"
C_BORDER     = "#1e1e3a"
C_GOLD       = "#ffd740"

# Plan definitions (for display — billing handled server-side)
PLANS = [
    {
        "id": "free", "name": "Free", "price": "$0", "period": "",
        "color": C_TEXT_DIM, "badge_color": C_BORDER, "enabled": True,
        "features": ["1 subdomain", "Dynamic DNS updates", "Desktop & web dashboard", "Community support"],
    },
    {
        "id": "pro", "name": "Dyno-IP Pro", "price": "$4.99", "period": "/mo",
        "color": C_ACCENT, "badge_color": "#003d47", "enabled": False,
        "features": ["10 subdomains", "Priority DNS propagation", "Advanced traffic analytics", "API access", "Email notifications"],
    },
    {
        "id": "web_pro", "name": "Web Pro", "price": "$9.99", "period": "/mo",
        "color": C_ACCENT2, "badge_color": "#1a0a4a", "enabled": False,
        "features": ["10 subdomains + 10 GB hosting", "PHP, Node.js, MySQL", "WordPress + frameworks", "Free SSL certificates", "Visual web editor"],
    },
    {
        "id": "web_enterprise", "name": "Web Enterprise", "price": "$14.99", "period": "/mo",
        "color": C_GOLD, "badge_color": "#3d3000", "enabled": False,
        "features": ["Everything in Web Pro", "1-year custom domain (IONOS)", "50 GB web storage", "Priority support", "Custom DNS records"],
    },
    {
        "id": "vpn_web", "name": "VPN Web Package", "price": "$19.99", "period": "/mo",
        "color": C_ERROR, "badge_color": "#3d0011", "enabled": False,
        "features": ["Everything in Enterprise", "4 CPU / 8 GB RAM VPS", "240 GB SSD storage", "Dedicated IP", "Full root access"],
    },
]

log = logging.getLogger("dynoip-gui")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


# ═══════════════════════════════════════════════════════════════════
# DEEP LINK / PROTOCOL HANDLER
# ═══════════════════════════════════════════════════════════════════

PROTOCOL_SCHEME = "dynoip"


def _get_exe_path() -> str:
    """Return the path to the current executable (frozen or script)."""
    if getattr(sys, "frozen", False):
        return sys.executable
    return os.path.abspath(sys.argv[0])


def register_protocol_handler():
    """Register dynoip:// as a custom URI scheme in the Windows registry (HKCU)."""
    exe_path = _get_exe_path()
    try:
        key_path = rf"Software\Classes\{PROTOCOL_SCHEME}"
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_path) as key:
            winreg.SetValueEx(key, "", 0, winreg.REG_SZ, "URL:DynoIP Protocol")
            winreg.SetValueEx(key, "URL Protocol", 0, winreg.REG_SZ, "")
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, rf"{key_path}\shell\open\command") as cmd_key:
            winreg.SetValueEx(cmd_key, "", 0, winreg.REG_SZ, f'"{exe_path}" "%1"')
        log.info("Registered dynoip:// protocol handler → %s", exe_path)
    except OSError as exc:
        log.warning("Failed to register protocol handler: %s", exc)


def parse_deep_link(url: str) -> dict | None:
    """Parse a dynoip://connect?endpoint=...&id=...&secret=... URL.

    Returns dict with keys {endpoint, newt_id, newt_secret} or None if invalid.
    """
    try:
        parsed = urlparse(url)
        if parsed.scheme != PROTOCOL_SCHEME:
            return None
        if parsed.netloc != "connect" and parsed.hostname != "connect":
            return None
        qs = parse_qs(parsed.query)
        endpoint = qs.get("endpoint", [None])[0]
        newt_id = qs.get("id", [None])[0]
        newt_secret = qs.get("secret", [None])[0]
        if not all([endpoint, newt_id, newt_secret]):
            return None
        return {"endpoint": endpoint, "newt_id": newt_id, "newt_secret": newt_secret}
    except Exception:
        return None


OAUTH_CALLBACK_FILE = os.path.join(CONFIG_DIR, "_oauth_pending.json")


def parse_oauth_deep_link(url: str) -> dict | None:
    """Parse a dynoip://auth?access_token=...&refresh_token=... URL.

    Returns dict with keys {access_token, refresh_token} or None if invalid.
    """
    try:
        parsed = urlparse(url)
        if parsed.scheme != PROTOCOL_SCHEME:
            return None
        if parsed.netloc != "auth" and parsed.hostname != "auth":
            return None
        qs = parse_qs(parsed.query)
        access_token = qs.get("access_token", [None])[0]
        refresh_token = qs.get("refresh_token", [None])[0]
        if not access_token or not refresh_token:
            return None
        return {"access_token": access_token, "refresh_token": refresh_token}
    except Exception:
        return None


def _write_oauth_callback(tokens: dict):
    """Write OAuth tokens to a well-known file so the running instance can pick them up."""
    os.makedirs(CONFIG_DIR, exist_ok=True)
    with open(OAUTH_CALLBACK_FILE, "w") as f:
        json.dump(tokens, f)


def _read_oauth_callback() -> dict | None:
    """Read and delete the OAuth callback file if it exists."""
    try:
        if not os.path.exists(OAUTH_CALLBACK_FILE):
            return None
        with open(OAUTH_CALLBACK_FILE, "r") as f:
            data = json.load(f)
        os.remove(OAUTH_CALLBACK_FILE)
        if data.get("access_token") and data.get("refresh_token"):
            return data
    except Exception:
        pass
    return None


# ═══════════════════════════════════════════════════════════════════
# NEWT PROCESS MANAGER  (secure — no creds on disk/logs)
# ═══════════════════════════════════════════════════════════════════

NEWT_DIR = os.path.join(os.environ.get("LOCALAPPDATA", CONFIG_DIR), "DynoIP")
NEWT_EXE = os.path.join(NEWT_DIR, "newt.exe")
NEWT_VERSION = "1.10.3"
NEWT_DOWNLOAD_URL = (
    f"https://github.com/fosrl/newt/releases/download/{NEWT_VERSION}"
    f"/newt_windows_amd64.exe"
)

# Windows: hide console window for subprocess
_CREATE_NO_WINDOW = 0x08000000


class NewtManager:
    """Manages Newt tunnel processes — one per tunnel_id.

    Security:
      • Credentials are NEVER written to disk — only held in-memory
      • Credentials are NEVER logged — only tunnel name appears in logs
      • Processes run with CREATE_NO_WINDOW (no visible console)
      • All processes are terminated on app exit
    """

    _instance: "NewtManager | None" = None

    def __init__(self):
        # tunnel_id → {process, thread, endpoint, newt_id, newt_secret, name}
        self._tunnels: dict[int, dict] = {}
        self._lock = threading.Lock()

    @classmethod
    def get(cls) -> "NewtManager":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @staticmethod
    def ensure_newt_binary(progress_cb=None) -> str:
        """Download newt.exe if it doesn't exist. Returns path."""
        os.makedirs(NEWT_DIR, exist_ok=True)
        if os.path.isfile(NEWT_EXE):
            return NEWT_EXE
        if progress_cb:
            progress_cb("Downloading Newt client...")
        resp = requests.get(NEWT_DOWNLOAD_URL, stream=True, timeout=60)
        resp.raise_for_status()
        tmp = NEWT_EXE + ".tmp"
        with open(tmp, "wb") as f:
            for chunk in resp.iter_content(8192):
                f.write(chunk)
        os.replace(tmp, NEWT_EXE)
        if progress_cb:
            progress_cb("Newt client ready")
        return NEWT_EXE

    def is_running(self, tunnel_id: int) -> bool:
        with self._lock:
            entry = self._tunnels.get(tunnel_id)
            if not entry:
                return False
            proc = entry.get("process")
            return proc is not None and proc.poll() is None

    def start(self, tunnel_id: int, name: str, endpoint: str,
              newt_id: str, newt_secret: str,
              log_cb=None) -> bool:
        """Launch newt.exe as a hidden subprocess. Returns True on success."""
        if self.is_running(tunnel_id):
            return True

        exe = self.ensure_newt_binary(
            progress_cb=lambda msg: log_cb(msg, "info") if log_cb else None
        )

        # Build args — credentials only in argv, never on disk
        args = [
            exe,
            "--endpoint", endpoint,
            "--id", newt_id,
            "--secret", newt_secret,
        ]

        try:
            proc = subprocess.Popen(
                args,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
                creationflags=_CREATE_NO_WINDOW,
            )
        except Exception as exc:
            if log_cb:
                log_cb(f"Failed to start tunnel '{name}': {exc}", "error")
            return False

        with self._lock:
            self._tunnels[tunnel_id] = {
                "process": proc,
                "name": name,
            }

        # Background reader — feeds filtered lines to log_cb
        def _reader():
            connected = False
            try:
                for raw_line in proc.stdout:
                    line = raw_line.decode("utf-8", errors="replace").strip()
                    if not line:
                        continue
                    # SECURITY: strip anything that looks like a secret or id
                    safe = line
                    if newt_id in safe:
                        safe = safe.replace(newt_id, "***")
                    if newt_secret in safe:
                        safe = safe.replace(newt_secret, "***")
                    # Suppress the spam — only log first "established" + errors
                    lower = safe.lower()
                    if "established successfully" in lower:
                        if not connected:
                            connected = True
                            if log_cb:
                                log_cb(f"Tunnel '{name}' connected", "success")
                        continue  # skip duplicates
                    if any(kw in lower for kw in ("error", "fatal", "failed", "disconnect")):
                        if log_cb:
                            log_cb(f"Tunnel '{name}': {safe}", "error")
                    # Other INFO lines are silently ignored
            except Exception:
                pass
            # Process ended
            with self._lock:
                self._tunnels.pop(tunnel_id, None)
            if log_cb:
                log_cb(f"Tunnel '{name}' disconnected", "warning")

        t = threading.Thread(target=_reader, daemon=True)
        t.start()

        if log_cb:
            log_cb(f"Starting tunnel '{name}'...", "info")
        return True

    def stop(self, tunnel_id: int, log_cb=None):
        """Terminate the Newt process for a tunnel."""
        with self._lock:
            entry = self._tunnels.pop(tunnel_id, None)
        if not entry:
            return
        proc = entry.get("process")
        name = entry.get("name", "?")
        if proc and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
        if log_cb:
            log_cb(f"Tunnel '{name}' stopped", "warning")

    def stop_all(self):
        """Terminate ALL running Newt processes (called on app exit)."""
        with self._lock:
            ids = list(self._tunnels.keys())
        for tid in ids:
            self.stop(tid)


# ═══════════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════════

def _create_tray_icon_image() -> Image.Image:
    """Generate a small 64x64 tray icon programmatically (cyan diamond on dark bg)."""
    img = Image.new("RGBA", (64, 64), (10, 10, 18, 255))
    draw = ImageDraw.Draw(img)
    cx, cy, r = 32, 32, 22
    draw.polygon([(cx, cy - r), (cx + r, cy), (cx, cy + r), (cx - r, cy)],
                 fill=(0, 229, 255, 255))
    ri = 12
    draw.polygon([(cx, cy - ri), (cx + ri, cy), (cx, cy + ri), (cx - ri, cy)],
                 fill=(10, 10, 18, 255))
    return img


def get_external_ip() -> str | None:
    """Fetch the user's external IP via a fast public service."""
    for url in ("https://api.ipify.org", "https://icanhazip.com", "https://ifconfig.me/ip"):
        try:
            with urlopen(Request(url), timeout=5) as r:
                return r.read().decode().strip()
        except Exception:
            continue
    return None


def relative_time(dt_str: str | None) -> str:
    """Convert ISO datetime string to human-friendly relative time."""
    if not dt_str:
        return "never"
    try:
        dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
        delta = datetime.now(timezone.utc) - dt
        secs = int(delta.total_seconds())
        if secs < 0:
            return "just now"
        if secs < 60:
            return f"{secs}s ago"
        if secs < 3600:
            return f"{secs // 60}m ago"
        if secs < 86400:
            return f"{secs // 3600}h ago"
        return f"{secs // 86400}d ago"
    except Exception:
        return str(dt_str)[:19]


# ═══════════════════════════════════════════════════════════════════
# API CLIENT
# ═══════════════════════════════════════════════════════════════════

class DynoAPI:
    """Thin wrapper around the Dyno-IP REST API with JWT refresh logic."""

    def __init__(self):
        self.access_token: str | None = None
        self.refresh_token: str | None = None
        self.session = requests.Session()
        self.session.headers["User-Agent"] = f"DynoIP-Desktop/{APP_VERSION}"
        self._load_tokens()

    # ── Persistence ──────────────────────────────────────────────

    def _load_tokens(self):
        try:
            with open(TOKEN_FILE) as f:
                data = json.load(f)
            self.access_token = data.get("access_token")
            self.refresh_token = data.get("refresh_token")
        except Exception:
            pass

    def _save_tokens(self):
        os.makedirs(CONFIG_DIR, exist_ok=True)
        with open(TOKEN_FILE, "w") as f:
            json.dump({"access_token": self.access_token, "refresh_token": self.refresh_token}, f)

    def _clear_tokens(self):
        self.access_token = None
        self.refresh_token = None
        try:
            os.remove(TOKEN_FILE)
        except OSError:
            pass

    # ── Auth helpers ─────────────────────────────────────────────

    def _auth_headers(self) -> dict:
        if self.access_token:
            return {"Authorization": f"Bearer {self.access_token}"}
        return {}

    def _try_refresh(self) -> bool:
        if not self.refresh_token:
            return False
        try:
            r = self.session.post(f"{API_BASE}/auth/refresh",
                                  json={"refresh_token": self.refresh_token}, timeout=10)
            if r.status_code == 200:
                data = r.json()
                self.access_token = data["access_token"]
                self.refresh_token = data["refresh_token"]
                self._save_tokens()
                return True
        except Exception:
            pass
        return False

    def _authed_request(self, method: str, path: str, **kwargs) -> requests.Response:
        url = f"{API_BASE}{path}"
        kwargs.setdefault("timeout", 15)
        r = self.session.request(method, url, headers=self._auth_headers(), **kwargs)
        if r.status_code == 401 and self._try_refresh():
            r = self.session.request(method, url, headers=self._auth_headers(), **kwargs)
        return r

    # ── Public API ───────────────────────────────────────────────

    def login(self, email: str, password: str) -> dict:
        r = self.session.post(f"{API_BASE}/auth/login",
                              json={"email": email, "password": password}, timeout=10)
        if r.status_code == 200:
            data = r.json()
            # Check for 2FA challenge
            if data.get("requires_2fa"):
                return {"ok": False, "requires_2fa": True, "challenge_token": data["challenge_token"]}
            self.access_token = data["access_token"]
            self.refresh_token = data["refresh_token"]
            self._save_tokens()
            return {"ok": True}
        detail = r.json().get("detail", "Login failed") if r.headers.get(
            "content-type", "").startswith("application/json") else r.text
        return {"ok": False, "error": str(detail)}

    def verify_2fa(self, challenge_token: str, code: str) -> dict:
        """Complete 2FA login with a 6-digit TOTP code."""
        r = self.session.post(f"{API_BASE}/auth/login/2fa",
                              json={"challenge_token": challenge_token, "code": code}, timeout=10)
        if r.status_code == 200:
            data = r.json()
            self.access_token = data["access_token"]
            self.refresh_token = data["refresh_token"]
            self._save_tokens()
            return {"ok": True}
        detail = r.json().get("detail", "Invalid 2FA code") if r.headers.get(
            "content-type", "").startswith("application/json") else r.text
        return {"ok": False, "error": str(detail)}

    def logout(self):
        self._clear_tokens()

    def is_logged_in(self) -> bool:
        return bool(self.access_token)

    def set_tokens(self, access_token: str, refresh_token: str):
        """Manually set tokens (e.g. from OAuth callback)."""
        self.access_token = access_token
        self.refresh_token = refresh_token
        self._save_tokens()

    def get_oauth_url(self, provider: str) -> dict:
        """Get OAuth authorization URL for the given provider (google/github)."""
        r = self.session.get(f"{API_BASE}/auth/oauth/{provider}",
                             params={"client": "desktop"}, timeout=10)
        if r.status_code == 200:
            return {"ok": True, "auth_url": r.json()["auth_url"]}
        detail = r.json().get("detail", "OAuth not available") if r.headers.get(
            "content-type", "").startswith("application/json") else r.text
        return {"ok": False, "error": str(detail)}

    def get_me(self) -> dict | None:
        r = self._authed_request("GET", "/auth/me")
        return r.json() if r.status_code == 200 else None

    def list_subdomains(self) -> list[dict]:
        r = self._authed_request("GET", "/ip/list")
        return r.json() if r.status_code == 200 else []

    def get_domains(self) -> dict:
        """Get available domains for registration."""
        r = self.session.get(f"{API_BASE}/ip/domains", timeout=10)
        return r.json() if r.status_code == 200 else {"domains": ["dyno-ip.com"], "default": "dyno-ip.com"}

    def create_subdomain(self, subdomain: str, domain: str | None = None) -> dict:
        payload: dict = {"subdomain": subdomain}
        if domain:
            payload["domain"] = domain
        r = self._authed_request("POST", "/ip/create", json=payload)
        if r.status_code == 201:
            return {"ok": True, **r.json()}
        detail = ""
        try:
            detail = r.json().get("detail", "")
        except Exception:
            detail = r.text
        return {"ok": False, "error": detail or f"HTTP {r.status_code}"}

    def delete_subdomain(self, subdomain: str) -> dict:
        r = self._authed_request("DELETE", f"/ip/{subdomain}")
        if r.status_code == 200:
            return {"ok": True}
        detail = ""
        try:
            detail = r.json().get("detail", "")
        except Exception:
            detail = r.text
        return {"ok": False, "error": detail or f"HTTP {r.status_code}"}

    def refresh_ip(self, subdomain: str, ip: str = "AUTO") -> dict:
        """Refresh IP via JWT-authenticated endpoint (works for all plans)."""
        payload = {}
        if ip and ip != "AUTO":
            payload["ip"] = ip
        r = self._authed_request("POST", f"/ip/refresh/{subdomain}", json=payload if payload else None)
        if r.status_code == 200:
            return {"ok": True, **r.json()}
        detail = ""
        try:
            detail = r.json().get("detail", "")
        except Exception:
            detail = r.text
        return {"ok": False, "error": detail or f"HTTP {r.status_code}"}

    def get_visitors(self, subdomain: str, limit: int = 50) -> dict:
        r = self._authed_request("GET", f"/ip/visitors/{subdomain}", params={"limit": limit})
        return r.json() if r.status_code == 200 else {}

    def get_history(self, subdomain: str, limit: int = 50) -> dict:
        r = self._authed_request("GET", f"/ip/history/{subdomain}", params={"limit": limit})
        return r.json() if r.status_code == 200 else {}

    def get_activity(self, limit: int = 100) -> dict:
        """Unified activity feed — IP changes, visitors, tunnel events, logins."""
        r = self._authed_request("GET", "/ip/activity", params={"limit": limit})
        return r.json() if r.status_code == 200 else {"events": [], "total": 0}

    # ── Tunnel API ───────────────────────────────────────────────

    def list_tunnels(self) -> list[dict]:
        r = self._authed_request("GET", "/tunnels")
        return r.json() if r.status_code == 200 else []

    def create_tunnel(self, name: str, subdomain: str, protocol: str = "http",
                      target_ip: str = "127.0.0.1", target_port: int = 80) -> dict:
        payload = {
            "name": name,
            "subdomain": subdomain,
            "protocol": protocol,
            "target_ip": target_ip,
            "target_port": target_port,
        }
        r = self._authed_request("POST", "/tunnels", json=payload)
        if r.status_code == 201:
            return {"ok": True, **r.json()}
        detail = ""
        try:
            detail = r.json().get("detail", "")
        except Exception:
            detail = r.text
        return {"ok": False, "error": detail or f"HTTP {r.status_code}"}

    def get_tunnel_install(self, tunnel_id: int, platform: str = "linux") -> dict:
        r = self._authed_request("GET", f"/tunnels/{tunnel_id}/install",
                                 params={"platform": platform})
        if r.status_code == 200:
            return {"ok": True, **r.json()}
        detail = ""
        try:
            detail = r.json().get("detail", "")
        except Exception:
            detail = r.text
        return {"ok": False, "error": detail or f"HTTP {r.status_code}"}

    def delete_tunnel(self, tunnel_id: int) -> dict:
        r = self._authed_request("DELETE", f"/tunnels/{tunnel_id}")
        if r.status_code == 200:
            return {"ok": True, **r.json()}
        detail = ""
        try:
            detail = r.json().get("detail", "")
        except Exception:
            detail = r.text
        return {"ok": False, "error": detail or f"HTTP {r.status_code}"}

    def sync_tunnel(self, tunnel_id: int) -> dict:
        r = self._authed_request("POST", f"/tunnels/{tunnel_id}/sync")
        if r.status_code == 200:
            return {"ok": True, **r.json()}
        detail = ""
        try:
            detail = r.json().get("detail", "")
        except Exception:
            detail = r.text
        return {"ok": False, "error": detail or f"HTTP {r.status_code}"}

    # ── Auto-update ──────────────────────────────────────────────

    def check_for_update(self) -> dict | None:
        """Check if a newer version is available. Returns release info or None."""
        try:
            r = self.session.get(f"{API_BASE}/client/version",
                                 params={"platform": "windows"}, timeout=10)
            if r.status_code == 200:
                data = r.json()
                if data.get("version") and data["version"] != APP_VERSION:
                    return data
        except Exception:
            pass
        return None


# ═══════════════════════════════════════════════════════════════════
# LOGIN FRAME
# ═══════════════════════════════════════════════════════════════════

class LoginFrame(ctk.CTkFrame):
    def __init__(self, master, api: DynoAPI, on_login_success):
        super().__init__(master, fg_color=C_BG, corner_radius=0)
        self.api = api
        self.on_login_success = on_login_success
        self._oauth_poll_id = None  # after() id for polling

        self._card = ctk.CTkFrame(self, fg_color=C_BG_CARD, corner_radius=16,
                            border_width=1, border_color=C_BORDER, width=400, height=620)
        self._card.place(relx=0.5, rely=0.5, anchor="center")
        self._card.pack_propagate(False)

        # Clean up any stale OAuth callback file from a previous attempt
        try:
            os.remove(OAUTH_CALLBACK_FILE)
        except OSError:
            pass

        self._build_login_form_inline()

    def _build_login_form_inline(self):
        """Build the standard login form inside the card."""
        inner = ctk.CTkFrame(self._card, fg_color="transparent")
        inner.pack(expand=True, fill="both", padx=40, pady=(30, 20))

        ctk.CTkLabel(inner, text="◈ DYNO-IP", font=("Consolas", 28, "bold"),
                      text_color=C_ACCENT).pack(pady=(0, 4))
        ctk.CTkLabel(inner, text="Dynamic DNS Control Panel",
                      font=("Segoe UI", 12), text_color=C_TEXT_DIM).pack(pady=(0, 16))

        # ── OAuth Buttons ────────────────────────────────────────
        self.google_btn = ctk.CTkButton(
            inner, text="  Continue with Google", height=40, corner_radius=8,
            fg_color="#1a1a2e", hover_color="#2a2a3e", border_width=1,
            border_color=C_BORDER, text_color=C_TEXT, font=("Segoe UI", 12),
            command=lambda: self._start_oauth("google"))
        self.google_btn.pack(fill="x", pady=(0, 6))

        self.github_btn = ctk.CTkButton(
            inner, text="  Continue with GitHub", height=40, corner_radius=8,
            fg_color="#1a1a2e", hover_color="#2a2a3e", border_width=1,
            border_color=C_BORDER, text_color=C_TEXT, font=("Segoe UI", 12),
            command=lambda: self._start_oauth("github"))
        self.github_btn.pack(fill="x", pady=(0, 12))

        # Divider
        div_frame = ctk.CTkFrame(inner, fg_color="transparent", height=20)
        div_frame.pack(fill="x", pady=(0, 12))
        ctk.CTkFrame(div_frame, fg_color=C_BORDER, height=1).place(
            relx=0, rely=0.5, relwidth=0.4, anchor="w")
        ctk.CTkLabel(div_frame, text="or", font=("Segoe UI", 10),
                      text_color=C_TEXT_DIM, fg_color=C_BG_CARD).place(
            relx=0.5, rely=0.5, anchor="center")
        ctk.CTkFrame(div_frame, fg_color=C_BORDER, height=1).place(
            relx=1.0, rely=0.5, relwidth=0.4, anchor="e")

        # ── Email / Password ─────────────────────────────────────
        ctk.CTkLabel(inner, text="EMAIL", font=("Segoe UI", 10, "bold"),
                      text_color=C_TEXT_DIM, anchor="w").pack(fill="x")
        self.email_entry = ctk.CTkEntry(inner, height=42, corner_radius=8,
                                         fg_color=C_BG_DARKER, border_color=C_BORDER,
                                         text_color=C_TEXT, placeholder_text="you@example.com")
        self.email_entry.pack(fill="x", pady=(2, 10))

        ctk.CTkLabel(inner, text="PASSWORD", font=("Segoe UI", 10, "bold"),
                      text_color=C_TEXT_DIM, anchor="w").pack(fill="x")
        self.pass_entry = ctk.CTkEntry(inner, height=42, corner_radius=8, show="•",
                                        fg_color=C_BG_DARKER, border_color=C_BORDER,
                                        text_color=C_TEXT, placeholder_text="••••••••")
        self.pass_entry.pack(fill="x", pady=(2, 4))

        forgot = ctk.CTkLabel(inner, text="Forgot password?", font=("Segoe UI", 11),
                               text_color=C_ACCENT, cursor="hand2")
        forgot.pack(anchor="e", pady=(0, 12))
        forgot.bind("<Button-1>", lambda e: webbrowser.open("https://dyno-ip.com/forgot-password"))

        self.login_btn = ctk.CTkButton(inner, text="SIGN IN", height=44, corner_radius=8,
                                        fg_color=C_ACCENT, hover_color="#00b8d4",
                                        text_color=C_BG, font=("Segoe UI", 13, "bold"),
                                        command=self._do_login)
        self.login_btn.pack(fill="x", pady=(0, 8))

        self.error_label = ctk.CTkLabel(inner, text="", font=("Segoe UI", 11),
                                         text_color=C_ERROR, wraplength=320)
        self.error_label.pack()

        # Register link
        reg_row = ctk.CTkFrame(inner, fg_color="transparent")
        reg_row.pack(pady=(4, 0))
        ctk.CTkLabel(reg_row, text="No account?", font=("Segoe UI", 11),
                      text_color=C_TEXT_DIM).pack(side="left")
        reg_link = ctk.CTkLabel(reg_row, text=" Sign up free", font=("Segoe UI", 11, "bold"),
                                 text_color=C_ACCENT, cursor="hand2")
        reg_link.pack(side="left")
        reg_link.bind("<Button-1>", lambda e: webbrowser.open("https://dyno-ip.com/login"))

        ctk.CTkLabel(inner, text=f"v{APP_VERSION}  •  Novamind Labs",
                      font=("Segoe UI", 10), text_color=C_TEXT_DIM).pack(side="bottom")

        self.email_entry.bind("<Return>", lambda e: self.pass_entry.focus())
        self.pass_entry.bind("<Return>", lambda e: self._do_login())

    # ── OAuth Flow ───────────────────────────────────────────────

    def _start_oauth(self, provider: str):
        """Initiate OAuth: get auth URL, open browser, start polling for callback."""
        self.error_label.configure(text="")
        self.google_btn.configure(state="disabled")
        self.github_btn.configure(state="disabled")
        btn = self.google_btn if provider == "google" else self.github_btn
        btn.configure(text=f"  Opening browser...")

        def worker():
            try:
                result = self.api.get_oauth_url(provider)
            except requests.exceptions.ConnectionError:
                result = {"ok": False, "error": "Cannot reach server."}
            except Exception as ex:
                result = {"ok": False, "error": str(ex)}
            self.after(0, lambda: self._oauth_url_ready(provider, result))

        threading.Thread(target=worker, daemon=True).start()

    def _oauth_url_ready(self, provider: str, result: dict):
        """Called when the OAuth URL has been fetched."""
        if not result.get("ok"):
            self.error_label.configure(text=result.get("error", "Failed to start OAuth"))
            self._reset_oauth_buttons()
            return

        # Open the auth URL in the default browser
        webbrowser.open(result["auth_url"])

        # Update button to show waiting state
        btn = self.google_btn if provider == "google" else self.github_btn
        btn.configure(text=f"  Waiting for browser...")

        # Start polling for the OAuth callback file
        self._oauth_poll_count = 0
        self._start_oauth_polling()

    def _start_oauth_polling(self):
        """Poll for OAuth callback tokens written by the second app instance."""
        tokens = _read_oauth_callback()
        if tokens:
            # Tokens received — complete login
            self.api.set_tokens(tokens["access_token"], tokens["refresh_token"])
            self._oauth_poll_id = None
            self.on_login_success()
            return

        self._oauth_poll_count += 1
        if self._oauth_poll_count > 120:  # ~2 minutes at 1s intervals
            self.error_label.configure(text="OAuth timed out. Please try again.")
            self._reset_oauth_buttons()
            self._oauth_poll_id = None
            return

        # Poll again in 1 second
        self._oauth_poll_id = self.after(1000, self._start_oauth_polling)

    def _reset_oauth_buttons(self):
        """Reset OAuth buttons to their default state."""
        self.google_btn.configure(state="normal", text="  Continue with Google")
        self.github_btn.configure(state="normal", text="  Continue with GitHub")

    def destroy(self):
        """Cancel OAuth polling on destroy."""
        if self._oauth_poll_id:
            self.after_cancel(self._oauth_poll_id)
            self._oauth_poll_id = None
        super().destroy()

    # ── Email / Password Login ───────────────────────────────────

    def _do_login(self):
        email = self.email_entry.get().strip()
        password = self.pass_entry.get().strip()
        if not email or not password:
            self.error_label.configure(text="Please enter email and password.")
            return
        self.login_btn.configure(state="disabled", text="Signing in...")
        self.error_label.configure(text="")

        def worker():
            try:
                result = self.api.login(email, password)
            except requests.exceptions.ConnectionError:
                result = {"ok": False, "error": "Cannot reach server. Check your internet connection."}
            except Exception as ex:
                result = {"ok": False, "error": str(ex)}
            self.after(0, lambda: self._login_done(result))

        threading.Thread(target=worker, daemon=True).start()

    def _login_done(self, result: dict):
        if result.get("ok"):
            self.on_login_success()
        elif result.get("requires_2fa"):
            self._show_2fa_entry(result["challenge_token"])
        else:
            self.error_label.configure(text=result.get("error", "Login failed"))
            self.login_btn.configure(state="normal", text="SIGN IN")

    # ── 2FA Verification ─────────────────────────────────────────

    def _show_2fa_entry(self, challenge_token: str):
        """Replace the login form with a 2FA code entry."""
        self._challenge_token = challenge_token

        # Clear card contents only (keep the card itself)
        for widget in self._card.winfo_children():
            widget.destroy()

        self._card.configure(height=420)

        inner = ctk.CTkFrame(self._card, fg_color="transparent")
        inner.pack(expand=True, fill="both", padx=40, pady=30)

        # Logo area
        ctk.CTkLabel(inner, text="🔐", font=("Segoe UI", 48)).pack(pady=(10, 4))
        ctk.CTkLabel(inner, text="Two-Factor Authentication",
                      font=("Segoe UI", 18, "bold"), text_color=C_ACCENT).pack(pady=(0, 4))
        ctk.CTkLabel(inner, text="Enter the 6-digit code from your\nauthenticator app",
                      font=("Segoe UI", 12), text_color=C_TEXT_DIM, justify="center").pack(pady=(0, 20))

        # Code entry
        ctk.CTkLabel(inner, text="VERIFICATION CODE", font=("Segoe UI", 10, "bold"),
                      text_color=C_TEXT_DIM, anchor="w").pack(fill="x")
        self.code_entry = ctk.CTkEntry(inner, height=50, corner_radius=8,
                                        fg_color=C_BG_DARKER, border_color=C_BORDER,
                                        text_color=C_TEXT, font=("Consolas", 22),
                                        placeholder_text="000000", justify="center")
        self.code_entry.pack(fill="x", pady=(4, 16))
        self.code_entry.focus()

        # Verify button
        self.verify_btn = ctk.CTkButton(inner, text="VERIFY", height=44, corner_radius=8,
                                         fg_color=C_ACCENT, hover_color="#00b8d4",
                                         text_color=C_BG, font=("Segoe UI", 13, "bold"),
                                         command=self._do_verify_2fa)
        self.verify_btn.pack(fill="x", pady=(0, 8))

        self.twofa_error = ctk.CTkLabel(inner, text="", font=("Segoe UI", 11),
                                         text_color=C_ERROR, wraplength=300)
        self.twofa_error.pack()

        # Back to login link
        back = ctk.CTkLabel(inner, text="← Back to login", font=("Segoe UI", 11),
                             text_color=C_ACCENT, cursor="hand2")
        back.pack(pady=(12, 0))
        back.bind("<Button-1>", lambda e: self._back_to_login())

        self.code_entry.bind("<Return>", lambda e: self._do_verify_2fa())

    def _do_verify_2fa(self):
        code = self.code_entry.get().strip()
        if not code or len(code) != 6 or not code.isdigit():
            self.twofa_error.configure(text="Enter a 6-digit code.")
            return
        self.verify_btn.configure(state="disabled", text="Verifying...")
        self.twofa_error.configure(text="")

        def worker():
            try:
                result = self.api.verify_2fa(self._challenge_token, code)
            except requests.exceptions.ConnectionError:
                result = {"ok": False, "error": "Cannot reach server."}
            except Exception as ex:
                result = {"ok": False, "error": str(ex)}
            self.after(0, lambda: self._verify_2fa_done(result))

        threading.Thread(target=worker, daemon=True).start()

    def _verify_2fa_done(self, result: dict):
        if result.get("ok"):
            self.on_login_success()
        else:
            self.twofa_error.configure(text=result.get("error", "Verification failed"))
            self.verify_btn.configure(state="normal", text="VERIFY")
            self.code_entry.delete(0, "end")
            self.code_entry.focus()

    def _back_to_login(self):
        """Rebuild the login form inside the existing card."""
        for widget in self._card.winfo_children():
            widget.destroy()
        self._card.configure(height=620)
        self._build_login_form_inline()


# ═══════════════════════════════════════════════════════════════════
# SUBDOMAIN CARD WIDGET
# ═══════════════════════════════════════════════════════════════════

class SubdomainCard(ctk.CTkFrame):
    """A single subdomain row inside the dashboard."""

    def __init__(self, master, data: dict, api: DynoAPI, log_callback, on_delete_done):
        super().__init__(master, fg_color=C_BG_CARD, corner_radius=12,
                         border_width=1, border_color=C_BORDER, height=90)
        self.pack_propagate(False)
        self.data = data
        self.api = api
        self.log_cb = log_callback
        self.on_delete_done = on_delete_done

        # Left: info
        left = ctk.CTkFrame(self, fg_color="transparent")
        left.pack(side="left", fill="both", expand=True, padx=16, pady=12)

        hostname = f"{data.get('subdomain', '?')}.{data.get('domain', 'dyno-ip.com')}"
        ctk.CTkLabel(left, text=hostname, font=("Consolas", 15, "bold"),
                      text_color=C_ACCENT, anchor="w").pack(fill="x")

        ip = data.get("current_ip") or "—"
        updated = relative_time(data.get("last_update"))
        self.info_label = ctk.CTkLabel(left, text=f"IP: {ip}   •   Updated: {updated}",
                                        font=("Segoe UI", 11), text_color=C_TEXT_DIM, anchor="w")
        self.info_label.pack(fill="x", pady=(2, 0))

        # Right: buttons
        right = ctk.CTkFrame(self, fg_color="transparent", width=280)
        right.pack(side="right", padx=12, pady=12)
        right.pack_propagate(False)

        btn_row = ctk.CTkFrame(right, fg_color="transparent")
        btn_row.pack(expand=True)

        self.refresh_btn = ctk.CTkButton(
            btn_row, text="⟳ Refresh", width=90, height=32, corner_radius=8,
            fg_color=C_ACCENT, hover_color="#00b8d4", text_color=C_BG,
            font=("Segoe UI", 11, "bold"), command=self._refresh_ip)
        self.refresh_btn.pack(side="left", padx=(0, 4))

        self.delete_btn = ctk.CTkButton(
            btn_row, text="✕", width=34, height=32, corner_radius=8,
            fg_color="#2a1020", hover_color=C_ERROR, text_color=C_ERROR,
            font=("Segoe UI", 13, "bold"), command=self._confirm_delete)
        self.delete_btn.pack(side="left")

        self.status_label = ctk.CTkLabel(right, text="", font=("Segoe UI", 10),
                                          text_color=C_SUCCESS)
        self.status_label.pack(pady=(4, 0))

    # ── Refresh IP ───────────────────────────────────────────────

    def _refresh_ip(self):
        subdomain = self.data.get("subdomain", "")
        if not subdomain:
            self.status_label.configure(text="No subdomain!", text_color=C_ERROR)
            return
        self.refresh_btn.configure(state="disabled", text="...")
        self.status_label.configure(text="")

        def worker():
            real_ip = get_external_ip() or "AUTO"
            result = self.api.refresh_ip(subdomain, ip=real_ip)
            self.after(0, lambda: self._refresh_done(result))
        threading.Thread(target=worker, daemon=True).start()

    def _refresh_done(self, result: dict):
        self.refresh_btn.configure(state="normal", text="⟳ Refresh")
        if result.get("ok"):
            new_ip = result.get("new_ip", "?")
            changed = result.get("changed", False)
            self.info_label.configure(text=f"IP: {new_ip}   •   Updated: just now")
            tag = "CHANGED" if changed else "unchanged"
            self.status_label.configure(text="✓ Updated", text_color=C_SUCCESS)
            self.log_cb(f"[{self.data.get('subdomain')}] IP → {new_ip} ({tag})",
                        "success" if changed else "info")
        else:
            err = result.get("error", "Failed")
            self.status_label.configure(text=f"✗ {err[:30]}", text_color=C_ERROR)
            self.log_cb(f"[{self.data.get('subdomain')}] Update failed: {err}", "error")

    # ── Delete ───────────────────────────────────────────────────

    def _confirm_delete(self):
        sub = self.data.get("subdomain", "?")
        domain = self.data.get("domain", "dyno-ip.com")

        popup = ctk.CTkToplevel(self)
        popup.title("Confirm Delete")
        popup.geometry("380x200")
        popup.configure(fg_color=C_BG)
        popup.attributes("-topmost", True)
        popup.resizable(False, False)

        inner = ctk.CTkFrame(popup, fg_color="transparent")
        inner.pack(expand=True, padx=30, pady=20)

        ctk.CTkLabel(inner, text="⚠  Delete Subdomain?", font=("Segoe UI", 16, "bold"),
                      text_color=C_WARNING).pack(pady=(0, 8))
        ctk.CTkLabel(inner, text=f"This will permanently release\n{sub}.{domain}",
                      font=("Segoe UI", 12), text_color=C_TEXT, justify="center").pack(pady=(0, 16))

        btn_row = ctk.CTkFrame(inner, fg_color="transparent")
        btn_row.pack()
        ctk.CTkButton(btn_row, text="Cancel", width=100, height=36, corner_radius=8,
                       fg_color=C_BORDER, hover_color="#2a2a4a", text_color=C_TEXT,
                       command=popup.destroy).pack(side="left", padx=(0, 8))
        ctk.CTkButton(btn_row, text="Delete", width=100, height=36, corner_radius=8,
                       fg_color=C_ERROR, hover_color="#d50000", text_color="#ffffff",
                       font=("Segoe UI", 12, "bold"),
                       command=lambda: self._do_delete(popup)).pack(side="left")

    def _do_delete(self, popup):
        popup.destroy()
        sub = self.data.get("subdomain", "")
        self.delete_btn.configure(state="disabled")

        def worker():
            result = self.api.delete_subdomain(sub)
            self.after(0, lambda: self._delete_done(result, sub))
        threading.Thread(target=worker, daemon=True).start()

    def _delete_done(self, result: dict, sub: str):
        if result.get("ok"):
            self.log_cb(f"Deleted subdomain: {sub}", "warning")
            self.on_delete_done()  # triggers reload
        else:
            self.delete_btn.configure(state="normal")
            err = result.get("error", "Failed")
            self.status_label.configure(text=f"✗ {err[:30]}", text_color=C_ERROR)
            self.log_cb(f"Delete failed [{sub}]: {err}", "error")


# ═══════════════════════════════════════════════════════════════════
# CREATE SUBDOMAIN DIALOG
# ═══════════════════════════════════════════════════════════════════

class CreateSubdomainDialog(ctk.CTkToplevel):
    def __init__(self, master, api: DynoAPI, on_created):
        super().__init__(master)
        self.api = api
        self.on_created = on_created
        self.title("Create Subdomain")
        self.geometry("440x310")
        self.configure(fg_color=C_BG)
        self.attributes("-topmost", True)
        self.resizable(False, False)

        inner = ctk.CTkFrame(self, fg_color="transparent")
        inner.pack(expand=True, fill="both", padx=30, pady=24)

        ctk.CTkLabel(inner, text="+ New Subdomain", font=("Segoe UI", 18, "bold"),
                      text_color=C_ACCENT).pack(pady=(0, 16))

        # Subdomain name
        ctk.CTkLabel(inner, text="SUBDOMAIN NAME", font=("Segoe UI", 10, "bold"),
                      text_color=C_TEXT_DIM, anchor="w").pack(fill="x")
        self.name_entry = ctk.CTkEntry(inner, height=40, corner_radius=8,
                                        fg_color=C_BG_DARKER, border_color=C_BORDER,
                                        text_color=C_TEXT, placeholder_text="myhost")
        self.name_entry.pack(fill="x", pady=(2, 12))

        # Domain picker
        ctk.CTkLabel(inner, text="DOMAIN", font=("Segoe UI", 10, "bold"),
                      text_color=C_TEXT_DIM, anchor="w").pack(fill="x")
        self.domain_var = ctk.StringVar(value="Loading...")
        self.domain_menu = ctk.CTkOptionMenu(inner, height=40, corner_radius=8,
                                              fg_color=C_BG_DARKER, button_color=C_BORDER,
                                              button_hover_color="#2a2a4a",
                                              text_color=C_TEXT, variable=self.domain_var,
                                              values=["Loading..."])
        self.domain_menu.pack(fill="x", pady=(2, 16))

        # Buttons
        btn_row = ctk.CTkFrame(inner, fg_color="transparent")
        btn_row.pack(fill="x")

        ctk.CTkButton(btn_row, text="Cancel", width=100, height=38, corner_radius=8,
                       fg_color=C_BORDER, hover_color="#2a2a4a", text_color=C_TEXT,
                       command=self.destroy).pack(side="left")

        self.create_btn = ctk.CTkButton(btn_row, text="CREATE", height=38, corner_radius=8,
                                         fg_color=C_ACCENT, hover_color="#00b8d4", text_color=C_BG,
                                         font=("Segoe UI", 13, "bold"),
                                         command=self._do_create)
        self.create_btn.pack(side="right", fill="x", expand=True, padx=(12, 0))

        self.error_label = ctk.CTkLabel(inner, text="", font=("Segoe UI", 11),
                                         text_color=C_ERROR, wraplength=360)
        self.error_label.pack(pady=(8, 0))

        self.name_entry.bind("<Return>", lambda e: self._do_create())

        # Load domains async
        threading.Thread(target=self._load_domains, daemon=True).start()

    def _load_domains(self):
        data = self.api.get_domains()
        domains = data.get("domains", ["dyno-ip.com"])
        default = data.get("default", domains[0] if domains else "dyno-ip.com")
        self.after(0, lambda: self._set_domains(domains, default))

    def _set_domains(self, domains: list[str], default: str):
        self.domain_menu.configure(values=domains)
        self.domain_var.set(default)

    def _do_create(self):
        name = self.name_entry.get().strip().lower()
        if not name:
            self.error_label.configure(text="Enter a subdomain name.")
            return
        if len(name) < 3:
            self.error_label.configure(text="Subdomain must be at least 3 characters.")
            return

        domain = self.domain_var.get()
        self.create_btn.configure(state="disabled", text="Creating...")
        self.error_label.configure(text="")

        def worker():
            result = self.api.create_subdomain(name, domain)
            self.after(0, lambda: self._create_done(result))
        threading.Thread(target=worker, daemon=True).start()

    def _create_done(self, result: dict):
        if result.get("ok"):
            self.on_created(result)
            self.destroy()
        else:
            self.create_btn.configure(state="normal", text="CREATE")
            self.error_label.configure(text=result.get("error", "Failed to create subdomain"))


# ═══════════════════════════════════════════════════════════════════
# TUNNEL CARD
# ═══════════════════════════════════════════════════════════════════

PROTOCOL_COLORS = {
    "http": C_SUCCESS,
    "https": C_ACCENT,
    "tcp": C_ACCENT2,
    "udp": C_WARNING,
}


class TunnelCard(ctk.CTkFrame):
    """Card displaying a single tunnel with Connect/Disconnect controls."""

    def __init__(self, master, data: dict, api: DynoAPI, log_callback, on_change):
        super().__init__(master, fg_color=C_BG_CARD, corner_radius=12,
                         border_width=1, border_color=C_BORDER, height=90)
        self.pack_propagate(False)
        self.data = data
        self.api = api
        self.log_cb = log_callback
        self.on_change = on_change
        self._newt = NewtManager.get()

        tunnel_id = data.get("id", "?")
        name = data.get("name", "untitled")
        domain = data.get("domain", "")
        protocol = data.get("protocol", "tcp")
        status = data.get("status", "unknown")
        port = data.get("target_port", "?")
        target_ip = data.get("target_ip", "127.0.0.1")
        is_active = data.get("is_active", False)
        proto_color = PROTOCOL_COLORS.get(protocol, C_TEXT_DIM)
        has_creds = data.get("has_install_command", False)

        # ── Left info ──
        left = ctk.CTkFrame(self, fg_color="transparent")
        left.pack(side="left", fill="both", expand=True, padx=12, pady=8)

        # Row 1: name + protocol badge
        row1 = ctk.CTkFrame(left, fg_color="transparent")
        row1.pack(fill="x")

        ctk.CTkLabel(row1, text=name, font=("Segoe UI", 14, "bold"),
                      text_color=C_TEXT).pack(side="left")

        badge_frame = ctk.CTkFrame(row1, fg_color=proto_color, corner_radius=6,
                                    width=50, height=20)
        badge_frame.pack(side="left", padx=(8, 0))
        badge_frame.pack_propagate(False)
        ctk.CTkLabel(badge_frame, text=protocol.upper(), font=("Consolas", 9, "bold"),
                      text_color=C_BG).place(relx=0.5, rely=0.5, anchor="center")

        # Status dot
        status_color = C_SUCCESS if is_active else C_TEXT_DIM
        ctk.CTkLabel(row1, text="●", font=("Segoe UI", 10),
                      text_color=status_color).pack(side="left", padx=(8, 0))
        ctk.CTkLabel(row1, text=status, font=("Segoe UI", 10),
                      text_color=C_TEXT_DIM).pack(side="left", padx=(2, 0))

        # Row 2: domain + target
        row2 = ctk.CTkFrame(left, fg_color="transparent")
        row2.pack(fill="x", pady=(4, 0))

        if domain:
            ctk.CTkLabel(row2, text=f"🌐 {domain}", font=("Consolas", 11),
                          text_color=C_ACCENT, cursor="hand2").pack(side="left")
        ctk.CTkLabel(row2, text=f"→ {target_ip}:{port}", font=("Consolas", 10),
                      text_color=C_TEXT_DIM).pack(side="left", padx=(12, 0))

        # ── Right buttons ──
        right = ctk.CTkFrame(self, fg_color="transparent", width=300)
        right.pack(side="right", padx=12, pady=8)
        right.pack_propagate(False)

        btn_row = ctk.CTkFrame(right, fg_color="transparent")
        btn_row.pack(anchor="e")

        # ── Connect / Disconnect button (primary action) ──
        if has_creds:
            running = self._newt.is_running(tunnel_id)
            self.connect_btn = ctk.CTkButton(
                btn_row,
                text="⏹ Disconnect" if running else "▶ Connect",
                width=110, height=30, corner_radius=6,
                fg_color=C_ERROR if running else C_SUCCESS,
                hover_color="#d50000" if running else "#00c853",
                text_color="#ffffff" if running else C_BG,
                font=("Segoe UI", 10, "bold"),
                command=self._toggle_connection)
            self.connect_btn.pack(side="left", padx=(0, 4))

        # Sync button
        self.sync_btn = ctk.CTkButton(
            btn_row, text="⟳", width=30, height=30, corner_radius=6,
            fg_color=C_BORDER, hover_color="#2a2a4a", text_color=C_TEXT,
            font=("Segoe UI", 12), command=self._do_sync)
        self.sync_btn.pack(side="left", padx=(0, 4))

        # Delete button
        self.delete_btn = ctk.CTkButton(
            btn_row, text="✕", width=30, height=30, corner_radius=6,
            fg_color=C_BORDER, hover_color=C_ERROR, text_color=C_ERROR,
            font=("Segoe UI", 12, "bold"), command=self._confirm_delete)
        self.delete_btn.pack(side="left")

        # Status label
        self.status_label = ctk.CTkLabel(right, text="", font=("Segoe UI", 10),
                                          text_color=C_TEXT_DIM, anchor="e")
        self.status_label.pack(anchor="e", pady=(4, 0))

    # ── Connect / Disconnect ─────────────────────────────────────

    def _toggle_connection(self):
        tunnel_id = self.data.get("id")
        if self._newt.is_running(tunnel_id):
            self._disconnect()
        else:
            self._connect()

    def _connect(self):
        tunnel_id = self.data.get("id")
        name = self.data.get("name", "?")
        endpoint = self.data.get("pangolin_endpoint", "")
        nid = self.data.get("newt_id", "")
        nsec = self.data.get("newt_secret", "")

        if not endpoint or not nid or not nsec:
            self.status_label.configure(text="✗ Missing tunnel credentials", text_color=C_ERROR)
            self.log_cb(f"Cannot connect '{name}' — no credentials", "error")
            return

        self.connect_btn.configure(state="disabled", text="Starting...")
        self.status_label.configure(text="", text_color=C_TEXT_DIM)

        def worker():
            try:
                ok = self._newt.start(
                    tunnel_id=tunnel_id,
                    name=name,
                    endpoint=endpoint,
                    newt_id=nid,
                    newt_secret=nsec,
                    log_cb=lambda msg, lvl: self.after(0, lambda m=msg, l=lvl: self.log_cb(m, l)),
                )
                self.after(0, lambda: self._connect_done(ok))
            except Exception as exc:
                self.after(0, lambda: self._connect_done(False, str(exc)))
        threading.Thread(target=worker, daemon=True).start()

    def _connect_done(self, ok: bool, err: str = ""):
        if ok:
            self.connect_btn.configure(
                state="normal", text="⏹ Disconnect",
                fg_color=C_ERROR, hover_color="#d50000", text_color="#ffffff")
            self.status_label.configure(text="● Running", text_color=C_SUCCESS)
        else:
            self.connect_btn.configure(state="normal", text="▶ Connect",
                                        fg_color=C_SUCCESS, hover_color="#00c853",
                                        text_color=C_BG)
            msg = err or "Failed to start"
            self.status_label.configure(text=f"✗ {msg[:30]}", text_color=C_ERROR)

    def _disconnect(self):
        tunnel_id = self.data.get("id")
        self.connect_btn.configure(state="disabled", text="Stopping...")

        def worker():
            self._newt.stop(
                tunnel_id,
                log_cb=lambda msg, lvl: self.after(0, lambda m=msg, l=lvl: self.log_cb(m, l)),
            )
            self.after(0, self._disconnect_done)
        threading.Thread(target=worker, daemon=True).start()

    def _disconnect_done(self):
        self.connect_btn.configure(
            state="normal", text="▶ Connect",
            fg_color=C_SUCCESS, hover_color="#00c853", text_color=C_BG)
        self.status_label.configure(text="", text_color=C_TEXT_DIM)

    def _do_sync(self):
        tunnel_id = self.data.get("id")
        self.sync_btn.configure(state="disabled", text="...")

        def worker():
            result = self.api.sync_tunnel(tunnel_id)
            self.after(0, lambda: self._sync_done(result))
        threading.Thread(target=worker, daemon=True).start()

    def _sync_done(self, result: dict):
        self.sync_btn.configure(state="normal", text="⟳ Sync")
        if result.get("ok"):
            self.log_cb(f"Synced tunnel: {self.data.get('name')}", "success")
            self.on_change()
        else:
            err = result.get("error", "Sync failed")
            self.status_label.configure(text=f"✗ {err[:30]}", text_color=C_ERROR)
            self.log_cb(f"Sync failed [{self.data.get('name')}]: {err}", "error")

    def _confirm_delete(self):
        name = self.data.get("name", "?")
        domain = self.data.get("domain", "")

        popup = ctk.CTkToplevel(self)
        popup.title("Confirm Delete")
        popup.geometry("420x220")
        popup.configure(fg_color=C_BG)
        popup.attributes("-topmost", True)
        popup.resizable(False, False)

        inner = ctk.CTkFrame(popup, fg_color="transparent")
        inner.pack(expand=True, padx=30, pady=20)

        ctk.CTkLabel(inner, text="⚠  Delete Tunnel?", font=("Segoe UI", 16, "bold"),
                      text_color=C_WARNING).pack(pady=(0, 8))
        ctk.CTkLabel(inner, text=f"This will delete tunnel '{name}'\nand remove {domain} from Pangolin.",
                      font=("Segoe UI", 12), text_color=C_TEXT, justify="center").pack(pady=(0, 16))

        btn_row = ctk.CTkFrame(inner, fg_color="transparent")
        btn_row.pack()
        ctk.CTkButton(btn_row, text="Cancel", width=100, height=36, corner_radius=8,
                       fg_color=C_BORDER, hover_color="#2a2a4a", text_color=C_TEXT,
                       command=popup.destroy).pack(side="left", padx=(0, 8))
        ctk.CTkButton(btn_row, text="Delete", width=100, height=36, corner_radius=8,
                       fg_color=C_ERROR, hover_color="#d50000", text_color="#ffffff",
                       font=("Segoe UI", 12, "bold"),
                       command=lambda: self._do_delete(popup)).pack(side="left")

    def _do_delete(self, popup):
        popup.destroy()
        tunnel_id = self.data.get("id")
        self.delete_btn.configure(state="disabled")

        def worker():
            # Stop the Newt process first (if running) before deleting the tunnel
            if self._newt.is_running(tunnel_id):
                self._newt.stop(
                    tunnel_id,
                    log_cb=lambda msg, lvl: self.after(0, lambda m=msg, l=lvl: self.log_cb(m, l)),
                )
            result = self.api.delete_tunnel(tunnel_id)
            self.after(0, lambda: self._delete_done(result))
        threading.Thread(target=worker, daemon=True).start()

    def _delete_done(self, result: dict):
        if result.get("ok"):
            self.log_cb(f"Deleted tunnel: {self.data.get('name')}", "warning")
            self.on_change()
        else:
            self.delete_btn.configure(state="normal")
            err = result.get("error", "Failed")
            self.status_label.configure(text=f"✗ {err[:30]}", text_color=C_ERROR)
            self.log_cb(f"Delete failed [{self.data.get('name')}]: {err}", "error")


# ═══════════════════════════════════════════════════════════════════
# CREATE TUNNEL DIALOG
# ═══════════════════════════════════════════════════════════════════

DEFAULT_PORTS = {"http": 80, "https": 443, "tcp": 22, "udp": 51820}


class CreateTunnelDialog(ctk.CTkToplevel):
    def __init__(self, master, api: DynoAPI, on_created):
        super().__init__(master)
        self.api = api
        self.on_created = on_created
        self.title("Create Tunnel")
        self.geometry("480x580")
        self.configure(fg_color=C_BG)
        self.attributes("-topmost", True)
        self.resizable(False, False)

        inner = ctk.CTkFrame(self, fg_color="transparent")
        inner.pack(expand=True, fill="both", padx=30, pady=20)

        ctk.CTkLabel(inner, text="+ New Tunnel", font=("Segoe UI", 18, "bold"),
                      text_color=C_ACCENT).pack(pady=(0, 12))

        # Tunnel name
        ctk.CTkLabel(inner, text="TUNNEL NAME", font=("Segoe UI", 10, "bold"),
                      text_color=C_TEXT_DIM, anchor="w").pack(fill="x")
        self.name_entry = ctk.CTkEntry(inner, height=38, corner_radius=8,
                                        fg_color=C_BG_DARKER, border_color=C_BORDER,
                                        text_color=C_TEXT, placeholder_text="my-web-server")
        self.name_entry.pack(fill="x", pady=(2, 8))

        # Subdomain
        ctk.CTkLabel(inner, text="SUBDOMAIN", font=("Segoe UI", 10, "bold"),
                      text_color=C_TEXT_DIM, anchor="w").pack(fill="x")
        sub_row = ctk.CTkFrame(inner, fg_color="transparent")
        sub_row.pack(fill="x", pady=(2, 8))
        self.sub_entry = ctk.CTkEntry(sub_row, height=38, corner_radius=8,
                                       fg_color=C_BG_DARKER, border_color=C_BORDER,
                                       text_color=C_TEXT, placeholder_text="mysite")
        self.sub_entry.pack(side="left", fill="x", expand=True)
        ctk.CTkLabel(sub_row, text=".dyno-ip.online", font=("Consolas", 11),
                      text_color=C_TEXT_DIM).pack(side="left", padx=(6, 0))

        # Protocol
        ctk.CTkLabel(inner, text="PROTOCOL", font=("Segoe UI", 10, "bold"),
                      text_color=C_TEXT_DIM, anchor="w").pack(fill="x")
        self.protocol_var = ctk.StringVar(value="http")
        self.protocol_menu = ctk.CTkOptionMenu(
            inner, height=38, corner_radius=8,
            fg_color=C_BG_DARKER, button_color=C_BORDER, button_hover_color="#2a2a4a",
            text_color=C_TEXT, variable=self.protocol_var,
            values=["http", "https", "tcp", "udp"],
            command=self._on_protocol_change)
        self.protocol_menu.pack(fill="x", pady=(2, 8))

        # Target Port + Target IP side by side
        port_ip_row = ctk.CTkFrame(inner, fg_color="transparent")
        port_ip_row.pack(fill="x", pady=(0, 8))

        port_col = ctk.CTkFrame(port_ip_row, fg_color="transparent")
        port_col.pack(side="left", fill="x", expand=True, padx=(0, 6))
        ctk.CTkLabel(port_col, text="TARGET PORT", font=("Segoe UI", 10, "bold"),
                      text_color=C_TEXT_DIM, anchor="w").pack(fill="x")
        self.port_entry = ctk.CTkEntry(port_col, height=38, corner_radius=8,
                                        fg_color=C_BG_DARKER, border_color=C_BORDER,
                                        text_color=C_TEXT, placeholder_text="80")
        self.port_entry.pack(fill="x", pady=(2, 0))
        self.port_entry.insert(0, "80")

        ip_col = ctk.CTkFrame(port_ip_row, fg_color="transparent")
        ip_col.pack(side="left", fill="x", expand=True, padx=(6, 0))
        ctk.CTkLabel(ip_col, text="TARGET IP", font=("Segoe UI", 10, "bold"),
                      text_color=C_TEXT_DIM, anchor="w").pack(fill="x")
        self.ip_entry = ctk.CTkEntry(ip_col, height=38, corner_radius=8,
                                      fg_color=C_BG_DARKER, border_color=C_BORDER,
                                      text_color=C_TEXT, placeholder_text="127.0.0.1")
        self.ip_entry.pack(fill="x", pady=(2, 0))
        self.ip_entry.insert(0, "127.0.0.1")

        # Buttons
        btn_row = ctk.CTkFrame(inner, fg_color="transparent")
        btn_row.pack(fill="x", pady=(14, 0))

        ctk.CTkButton(btn_row, text="Cancel", width=100, height=38, corner_radius=8,
                       fg_color=C_BORDER, hover_color="#2a2a4a", text_color=C_TEXT,
                       command=self.destroy).pack(side="left")

        self.create_btn = ctk.CTkButton(
            btn_row, text="CREATE TUNNEL", height=38, corner_radius=8,
            fg_color=C_ACCENT, hover_color="#00b8d4", text_color=C_BG,
            font=("Segoe UI", 13, "bold"), command=self._do_create)
        self.create_btn.pack(side="right", fill="x", expand=True, padx=(12, 0))

        self.error_label = ctk.CTkLabel(inner, text="", font=("Segoe UI", 11),
                                         text_color=C_ERROR, wraplength=400)
        self.error_label.pack(pady=(8, 0))

        self.name_entry.bind("<Return>", lambda e: self._do_create())
        self.sub_entry.bind("<Return>", lambda e: self._do_create())

    def _on_protocol_change(self, proto: str):
        """Auto-fill the default port for the selected protocol."""
        default_port = DEFAULT_PORTS.get(proto, 80)
        self.port_entry.delete(0, "end")
        self.port_entry.insert(0, str(default_port))

    def _do_create(self):
        import re
        name = self.name_entry.get().strip()
        subdomain = self.sub_entry.get().strip().lower()
        # Sanitise: underscores/spaces → hyphens, strip invalid chars
        subdomain = re.sub(r"[^a-z0-9-]", "-", subdomain)
        subdomain = re.sub(r"-{2,}", "-", subdomain).strip("-")
        self.sub_entry.delete(0, "end")
        self.sub_entry.insert(0, subdomain)

        protocol = self.protocol_var.get()
        target_ip = self.ip_entry.get().strip() or "127.0.0.1"
        port_str = self.port_entry.get().strip()

        if not name or len(name) < 3:
            self.error_label.configure(text="Tunnel name must be at least 3 characters.")
            return
        if not subdomain or len(subdomain) < 3:
            self.error_label.configure(text="Subdomain must be at least 3 characters (a-z, 0-9, hyphens only).")
            return
        try:
            port = int(port_str)
            if port < 1 or port > 65535:
                raise ValueError
        except (ValueError, TypeError):
            self.error_label.configure(text="Port must be a number between 1-65535.")
            return

        self.create_btn.configure(state="disabled", text="Provisioning...")
        self.error_label.configure(text="")

        def worker():
            result = self.api.create_tunnel(name, subdomain, protocol, target_ip, port)
            self.after(0, lambda: self._create_done(result))
        threading.Thread(target=worker, daemon=True).start()

    def _create_done(self, result: dict):
        if result.get("ok"):
            self.on_created(result)
            self.destroy()
        else:
            self.create_btn.configure(state="normal", text="CREATE TUNNEL")
            self.error_label.configure(text=result.get("error", "Failed to create tunnel"))


# ═══════════════════════════════════════════════════════════════════
# PLANS TAB
# ═══════════════════════════════════════════════════════════════════

class PlansFrame(ctk.CTkScrollableFrame):
    """Displays plan tiers with the user's current plan highlighted."""

    def __init__(self, master, current_plan: str = "free"):
        super().__init__(master, fg_color=C_BG, scrollbar_button_color=C_BORDER)
        self.current_plan = current_plan.lower()

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", pady=(8, 16), padx=4)
        ctk.CTkLabel(header, text="PLANS & PRICING", font=("Segoe UI", 14, "bold"),
                      text_color=C_TEXT).pack(side="left")

        for plan in PLANS:
            self._render_plan_card(plan)

    def _render_plan_card(self, plan: dict):
        is_current = plan["id"] == self.current_plan
        is_enabled = plan.get("enabled", True)
        border_color = plan["color"] if is_current else C_BORDER

        card = ctk.CTkFrame(self, fg_color=C_BG_CARD, corner_radius=12,
                            border_width=2 if is_current else 1, border_color=border_color)
        card.pack(fill="x", padx=4, pady=4)

        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="x", padx=20, pady=16)

        # Top row: name + price + badge
        top = ctk.CTkFrame(inner, fg_color="transparent")
        top.pack(fill="x")

        name_color = plan["color"] if is_enabled else C_TEXT_DIM
        ctk.CTkLabel(top, text=plan["name"], font=("Segoe UI", 16, "bold"),
                      text_color=name_color).pack(side="left")

        price_txt = f"{plan['price']}{plan['period']}"
        ctk.CTkLabel(top, text=price_txt, font=("Consolas", 15, "bold"),
                      text_color=C_TEXT if is_enabled else C_TEXT_DIM).pack(side="left", padx=(12, 0))

        if is_current:
            badge = ctk.CTkLabel(top, text=" CURRENT ", font=("Segoe UI", 10, "bold"),
                                  text_color=plan["color"], fg_color=plan["badge_color"],
                                  corner_radius=6)
            badge.pack(side="right")
        elif not is_enabled:
            badge = ctk.CTkLabel(top, text=" COMING SOON ", font=("Segoe UI", 10, "bold"),
                                  text_color=C_TEXT_DIM, fg_color=C_BORDER,
                                  corner_radius=6)
            badge.pack(side="right")

        # Features
        feat_frame = ctk.CTkFrame(inner, fg_color="transparent")
        feat_frame.pack(fill="x", pady=(8, 0))

        feat_color = C_TEXT_DIM if is_enabled else "#3a3a5a"
        for feat in plan["features"]:
            ctk.CTkLabel(feat_frame, text=f"  ✓  {feat}", font=("Segoe UI", 11),
                          text_color=feat_color, anchor="w").pack(fill="x")

        # Upgrade button (only for enabled plans, not current, not free)
        if is_enabled and not is_current and plan["id"] != "free":
            ctk.CTkButton(inner, text="Upgrade →", width=120, height=32, corner_radius=8,
                           fg_color=plan["color"], hover_color=plan["badge_color"],
                           text_color=C_BG if plan["color"] != C_GOLD else "#000",
                           font=("Segoe UI", 11, "bold"),
                           command=lambda: webbrowser.open("https://dyno-ip.com/dashboard")
                           ).pack(anchor="e", pady=(10, 0))


# ═══════════════════════════════════════════════════════════════════
# DASHBOARD FRAME
# ═══════════════════════════════════════════════════════════════════

class DashboardFrame(ctk.CTkFrame):
    def __init__(self, master, api: DynoAPI, on_logout):
        super().__init__(master, fg_color=C_BG, corner_radius=0)
        self.api = api
        self.on_logout = on_logout
        self._stop = threading.Event()
        self._cards: list[SubdomainCard] = []
        self._user_plan = "free"

        # ── Top bar ──
        topbar = ctk.CTkFrame(self, fg_color=C_BG_CARD, height=56, corner_radius=0)
        topbar.pack(fill="x")
        topbar.pack_propagate(False)

        ctk.CTkLabel(topbar, text="◈ DYNO-IP", font=("Consolas", 18, "bold"),
                      text_color=C_ACCENT).pack(side="left", padx=16)

        self.user_label = ctk.CTkLabel(topbar, text="", font=("Segoe UI", 12),
                                        text_color=C_TEXT_DIM)
        self.user_label.pack(side="left", padx=8)

        self.ip_label = ctk.CTkLabel(topbar, text="", font=("Consolas", 11),
                                      text_color=C_TEXT_DIM)
        self.ip_label.pack(side="left", padx=(20, 0))

        logout_btn = ctk.CTkButton(topbar, text="Logout", width=80, height=32,
                                    corner_radius=8, fg_color=C_BORDER, hover_color="#2a2a4a",
                                    text_color=C_TEXT, font=("Segoe UI", 11),
                                    command=self._handle_logout)
        logout_btn.pack(side="right", padx=16)

        ctk.CTkFrame(self, fg_color=C_BORDER, height=1).pack(fill="x")

        # ── Tabs ──
        self.tab_view = ctk.CTkTabview(self, fg_color=C_BG, segmented_button_fg_color=C_BG_CARD,
                                        segmented_button_selected_color=C_ACCENT,
                                        segmented_button_selected_hover_color="#00b8d4",
                                        segmented_button_unselected_color=C_BG_CARD,
                                        segmented_button_unselected_hover_color=C_BORDER,
                                        text_color=C_BG, corner_radius=0)
        self.tab_view.pack(fill="both", expand=True)

        self.tab_subs = self.tab_view.add("  Subdomains  ")
        self.tab_tunnels = self.tab_view.add("  Tunnels  ")
        self.tab_log = self.tab_view.add("  Activity Log  ")
        self.tab_plans = self.tab_view.add("  Plans  ")

        # ── Subdomains tab ──
        sub_header = ctk.CTkFrame(self.tab_subs, fg_color="transparent")
        sub_header.pack(fill="x", padx=12, pady=(8, 4))

        ctk.CTkLabel(sub_header, text="YOUR SUBDOMAINS", font=("Segoe UI", 11, "bold"),
                      text_color=C_TEXT_DIM).pack(side="left")

        self.add_btn = ctk.CTkButton(sub_header, text="+ New Subdomain", width=150, height=32,
                                      corner_radius=8, fg_color=C_ACCENT, hover_color="#00b8d4",
                                      text_color=C_BG, font=("Segoe UI", 11, "bold"),
                                      command=self._open_create_dialog)
        self.add_btn.pack(side="right")

        self.subs_scroll = ctk.CTkScrollableFrame(self.tab_subs, fg_color=C_BG,
                                                    scrollbar_button_color=C_BORDER)
        self.subs_scroll.pack(fill="both", expand=True, padx=12, pady=(0, 8))

        self.loading_label = ctk.CTkLabel(self.subs_scroll, text="Loading subdomains...",
                                           font=("Segoe UI", 13), text_color=C_TEXT_DIM)
        self.loading_label.pack(pady=40)

        # ── Tunnels tab ──
        tunl_header = ctk.CTkFrame(self.tab_tunnels, fg_color="transparent")
        tunl_header.pack(fill="x", padx=12, pady=(8, 4))

        ctk.CTkLabel(tunl_header, text="YOUR TUNNELS", font=("Segoe UI", 11, "bold"),
                      text_color=C_TEXT_DIM).pack(side="left")

        self.add_tunnel_btn = ctk.CTkButton(
            tunl_header, text="+ New Tunnel", width=140, height=32,
            corner_radius=8, fg_color=C_ACCENT2, hover_color="#5e35b1",
            text_color="#ffffff", font=("Segoe UI", 11, "bold"),
            command=self._open_tunnel_dialog)
        self.add_tunnel_btn.pack(side="right")

        self.tunnels_scroll = ctk.CTkScrollableFrame(
            self.tab_tunnels, fg_color=C_BG, scrollbar_button_color=C_BORDER)
        self.tunnels_scroll.pack(fill="both", expand=True, padx=12, pady=(0, 8))

        self.tunnel_loading = ctk.CTkLabel(
            self.tunnels_scroll, text="Loading tunnels...",
            font=("Segoe UI", 13), text_color=C_TEXT_DIM)
        self.tunnel_loading.pack(pady=40)
        self._tunnel_cards: list[TunnelCard] = []

        # ── Activity Log tab ──
        log_outer = ctk.CTkFrame(self.tab_log, fg_color="transparent")
        log_outer.pack(fill="both", expand=True, padx=12, pady=8)

        # --- Server-side activity feed (top ~60%) ---
        feed_header = ctk.CTkFrame(log_outer, fg_color="transparent")
        feed_header.pack(fill="x", pady=(0, 4))
        ctk.CTkLabel(feed_header, text="ACTIVITY FEED", font=("Segoe UI", 11, "bold"),
                      text_color=C_TEXT_DIM).pack(side="left")

        # Kind filter
        self._activity_filter = ctk.StringVar(value="all")
        filter_menu = ctk.CTkOptionMenu(
            feed_header, height=26, width=120, corner_radius=6,
            fg_color=C_BG_DARKER, button_color=C_BORDER, button_hover_color="#2a2a4a",
            text_color=C_TEXT, font=("Segoe UI", 10),
            variable=self._activity_filter,
            values=["all", "ip_change", "visitor", "tunnel_status", "login"],
            command=lambda _: self._filter_activity_feed())
        filter_menu.pack(side="left", padx=(8, 0))

        self.refresh_feed_btn = ctk.CTkButton(
            feed_header, text="⟳ Refresh", width=90, height=26, corner_radius=6,
            fg_color=C_ACCENT, hover_color="#00b8d4", text_color=C_BG,
            font=("Segoe UI", 10, "bold"), command=self._load_activity_feed)
        self.refresh_feed_btn.pack(side="right")

        self.feed_count_label = ctk.CTkLabel(feed_header, text="", font=("Segoe UI", 10),
                                              text_color=C_TEXT_DIM)
        self.feed_count_label.pack(side="right", padx=(0, 8))

        self.activity_textbox = ctk.CTkTextbox(
            log_outer, fg_color=C_BG_DARKER, text_color=C_TEXT,
            font=("Consolas", 10), corner_radius=8,
            border_width=1, border_color=C_BORDER, wrap="none")
        self.activity_textbox.pack(fill="both", expand=True)
        self.activity_textbox.configure(state="disabled")
        self._cached_activity: list[dict] = []

        # --- Session log (bottom ~40%) ---
        ctk.CTkFrame(log_outer, fg_color=C_BORDER, height=1).pack(fill="x", pady=6)
        ctk.CTkLabel(log_outer, text="SESSION LOG", font=("Segoe UI", 10, "bold"),
                      text_color=C_TEXT_DIM).pack(anchor="w", pady=(0, 4))

        self.log_textbox = ctk.CTkTextbox(log_outer, fg_color=C_BG_DARKER, text_color=C_TEXT,
                                           font=("Consolas", 10), corner_radius=8,
                                           border_width=1, border_color=C_BORDER, height=150)
        self.log_textbox.pack(fill="x")
        self.log_textbox.configure(state="disabled")

        # ── Plans tab (filled after user info loads) ──
        self._plans_frame: PlansFrame | None = None

        # Start loading data
        self._load_user_info()
        self._load_subdomains()
        self._load_tunnels()
        self._detect_ip()
        self._load_activity_feed()
        self._start_auto_refresh()

    def _add_log(self, message: str, level: str = "info"):
        ts = datetime.now().strftime("%H:%M:%S")
        prefix_map = {"success": "✓", "error": "✗", "warning": "⚠", "info": "ℹ"}
        prefix = prefix_map.get(level, "ℹ")
        self.log_textbox.configure(state="normal")
        self.log_textbox.insert("end", f"  [{ts}] {prefix} {message}\n")
        self.log_textbox.see("end")
        self.log_textbox.configure(state="disabled")

    # ── Activity Feed (server-side) ──────────────────────────────

    def _load_activity_feed(self):
        self.refresh_feed_btn.configure(state="disabled", text="...")

        def worker():
            data = self.api.get_activity(limit=200)
            self.after(0, lambda: self._render_activity_feed(data))
        threading.Thread(target=worker, daemon=True).start()

    def _render_activity_feed(self, data: dict):
        self.refresh_feed_btn.configure(state="normal", text="⟳ Refresh")
        events = data.get("events", [])
        total = data.get("total", 0)
        self._cached_activity = events
        self.feed_count_label.configure(text=f"{total} events")
        self._filter_activity_feed()

    def _filter_activity_feed(self):
        kind_filter = self._activity_filter.get()
        events = self._cached_activity
        if kind_filter != "all":
            events = [e for e in events if e.get("kind") == kind_filter]

        KIND_ICONS = {
            "ip_change": "🔄",
            "visitor": "👁",
            "tunnel_status": "🔗",
            "login": "🔐",
        }
        KIND_COLORS = {
            "ip_change": C_SUCCESS,
            "visitor": C_ACCENT,
            "tunnel_status": C_ACCENT2,
            "login": C_WARNING,
        }

        self.activity_textbox.configure(state="normal")
        self.activity_textbox.delete("1.0", "end")

        if not events:
            self.activity_textbox.insert("end", "  No activity events yet.\n")
        else:
            # Header line
            self.activity_textbox.insert(
                "end",
                f"  {'TIME':>10}  {'TYPE':<16}  {'SOURCE IP':<18}  {'SUB/TUNNEL':<16}  DETAIL\n"
            )
            self.activity_textbox.insert("end", "  " + "─" * 90 + "\n")

            for ev in events:
                kind = ev.get("kind", "?")
                icon = KIND_ICONS.get(kind, "•")
                ts_raw = ev.get("timestamp", "")
                # Parse timestamp
                ts_str = ""
                if ts_raw:
                    try:
                        if isinstance(ts_raw, str):
                            # "2026-03-21T12:34:56"
                            ts_str = ts_raw[11:19] if len(ts_raw) >= 19 else ts_raw[:8]
                        else:
                            ts_str = str(ts_raw)[:8]
                    except Exception:
                        ts_str = "?"

                source_ip = ev.get("source_ip") or ""
                country = ev.get("country") or ""
                if country:
                    source_ip = f"{country} {source_ip}"
                sub = ev.get("subdomain") or ev.get("tunnel_name") or ""
                title = ev.get("title", "")
                detail = ev.get("detail") or ""

                line = f"  {ts_str:>10}  {icon} {kind:<14}  {source_ip:<18}  {sub:<16}  {title}"
                if detail:
                    line += f"  •  {detail}"
                self.activity_textbox.insert("end", line + "\n")

        self.activity_textbox.configure(state="disabled")

    def _load_user_info(self):
        def worker():
            me = self.api.get_me()
            if me:
                self.after(0, lambda: self._set_user_info(me))
        threading.Thread(target=worker, daemon=True).start()

    def _set_user_info(self, me: dict):
        plan = me.get("plan", "free")
        self._user_plan = plan
        self.user_label.configure(text=f"{me.get('username', '?')}  ({plan.upper()})")
        # Build plans tab
        if self._plans_frame:
            self._plans_frame.destroy()
        self._plans_frame = PlansFrame(self.tab_plans, current_plan=plan)
        self._plans_frame.pack(fill="both", expand=True, padx=12, pady=8)

    def _detect_ip(self):
        def worker():
            ip = get_external_ip()
            if ip:
                self.after(0, lambda: self.ip_label.configure(text=f"Your IP: {ip}"))
                self.after(0, lambda: self._add_log(f"Detected external IP: {ip}", "info"))
        threading.Thread(target=worker, daemon=True).start()

    def _load_subdomains(self):
        def worker():
            subs = self.api.list_subdomains()
            self.after(0, lambda: self._render_subdomains(subs))
        threading.Thread(target=worker, daemon=True).start()

    def _render_subdomains(self, subdomains: list[dict]):
        for card in self._cards:
            card.destroy()
        self._cards.clear()
        self.loading_label.pack_forget()

        # Clear stale children
        for child in self.subs_scroll.winfo_children():
            child.destroy()

        if not subdomains:
            ctk.CTkLabel(self.subs_scroll, text="No subdomains yet — click '+ New Subdomain' above!",
                          font=("Segoe UI", 13), text_color=C_TEXT_DIM,
                          justify="center").pack(pady=40)
            self._add_log("No subdomains found", "warning")
            return

        for sub in subdomains:
            card = SubdomainCard(self.subs_scroll, sub, self.api, self._add_log, self._load_subdomains)
            card.pack(fill="x", pady=4)
            self._cards.append(card)

        self._add_log(f"Loaded {len(subdomains)} subdomain(s)", "success")

    def _open_create_dialog(self):
        CreateSubdomainDialog(self, self.api, self._on_subdomain_created)

    # ── Tunnels ──────────────────────────────────────────────────

    def _load_tunnels(self):
        def worker():
            tunnels = self.api.list_tunnels()
            self.after(0, lambda: self._render_tunnels(tunnels))
        threading.Thread(target=worker, daemon=True).start()

    def _render_tunnels(self, tunnels: list[dict]):
        for card in self._tunnel_cards:
            card.destroy()
        self._tunnel_cards.clear()
        self.tunnel_loading.pack_forget()

        for child in self.tunnels_scroll.winfo_children():
            child.destroy()

        if not tunnels:
            ctk.CTkLabel(self.tunnels_scroll,
                          text="No tunnels yet — click '+ New Tunnel' above!",
                          font=("Segoe UI", 13), text_color=C_TEXT_DIM,
                          justify="center").pack(pady=40)
            self._add_log("No tunnels found", "info")
            return

        for t in tunnels:
            card = TunnelCard(self.tunnels_scroll, t, self.api,
                              self._add_log, self._load_tunnels)
            card.pack(fill="x", pady=4)
            self._tunnel_cards.append(card)

        self._add_log(f"Loaded {len(tunnels)} tunnel(s)", "success")

    def _open_tunnel_dialog(self):
        CreateTunnelDialog(self, self.api, self._on_tunnel_created)

    def _on_tunnel_created(self, result: dict):
        tunnel = result.get("tunnel", {})
        name = tunnel.get("name", "?")
        domain = result.get("full_domain", "?")
        self._add_log(f"Created tunnel: {name} → {domain}", "success")
        self._load_tunnels()

    def _on_subdomain_created(self, result: dict):
        sub = result.get("subdomain", "?")
        domain = result.get("domain", "?")
        self._add_log(f"Created subdomain: {sub}.{domain}", "success")
        self._load_subdomains()

    def _start_auto_refresh(self):
        def loop():
            while not self._stop.is_set():
                self._stop.wait(AUTO_REFRESH_INTERVAL)
                if self._stop.is_set():
                    break
                self.after(0, lambda: self._add_log("Auto-refreshing all subdomains...", "info"))
                subs = self.api.list_subdomains()
                for sub in subs:
                    if self._stop.is_set():
                        break
                    name = sub.get("subdomain", "")
                    if name:
                        real_ip = get_external_ip() or "AUTO"
                        result = self.api.refresh_ip(name, ip=real_ip)
                        if result.get("ok"):
                            changed = result.get("changed", False)
                            new_ip = result.get("new_ip", "?")
                            if changed:
                                self.after(0, lambda n=name, ip=new_ip:
                                           self._add_log(f"[{n}] IP changed → {ip}", "success"))
                        else:
                            err = result.get("error", "?")
                            self.after(0, lambda n=name, e=err:
                                       self._add_log(f"[{n}] Auto-refresh failed: {e}", "error"))
                self.after(0, self._load_subdomains)
                # Also refresh the activity feed with latest server-side events
                self.after(0, self._load_activity_feed)

        self._bg_thread = threading.Thread(target=loop, daemon=True)
        self._bg_thread.start()

    def _handle_logout(self):
        self._stop.set()
        self.api.logout()
        self.on_logout()

    def destroy(self):
        self._stop.set()
        super().destroy()


# ═══════════════════════════════════════════════════════════════════
# MAIN APPLICATION (with system tray)
# ═══════════════════════════════════════════════════════════════════

class DynoIPApp(ctk.CTk):
    def __init__(self, deep_link: dict | None = None):
        super().__init__()

        self._deep_link = deep_link  # {endpoint, newt_id, newt_secret} or None

        self.title("Dyno-IP — Dynamic DNS")
        self.geometry("860x620")
        self.minsize(700, 500)
        self.configure(fg_color=C_BG)

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("dark-blue")

        # Window icon
        try:
            icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dynoip.ico")
            if os.path.exists(icon_path):
                self.iconbitmap(icon_path)
        except Exception:
            pass

        # API client
        self.api = DynoAPI()

        # Current frame
        self.current_frame: ctk.CTkFrame | None = None

        # ── System tray ──
        self._tray_icon: pystray.Icon | None = None
        self._tray_image = _create_tray_icon_image()
        self._setup_tray()

        # Override close & minimize → tray
        self.protocol("WM_DELETE_WINDOW", self._hide_to_tray)
        self.bind("<Unmap>", self._on_minimize)

        # Route to login or dashboard
        if self.api.is_logged_in():
            self._validate_session()
        else:
            self._show_login()

    # ── System Tray ──────────────────────────────────────────────

    def _setup_tray(self):
        menu = pystray.Menu(
            pystray.MenuItem("Show Dyno-IP", self._show_from_tray, default=True),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit", self._quit_app),
        )
        self._tray_icon = pystray.Icon("DynoIP", self._tray_image, "Dyno-IP", menu)
        threading.Thread(target=self._tray_icon.run, daemon=True).start()

    def _hide_to_tray(self):
        """Hide window to system tray instead of closing."""
        self.withdraw()

    def _on_minimize(self, event=None):
        """Intercept minimize — send to tray."""
        if self.state() == "iconic":
            self.after(10, self._hide_to_tray)

    def _show_from_tray(self, icon=None, item=None):
        """Restore window from system tray."""
        self.after(0, self._do_show)

    def _do_show(self):
        self.deiconify()
        self.state("normal")
        self.lift()
        self.focus_force()

    def _quit_app(self, icon=None, item=None):
        """Actually quit — stop tray icon, kill all Newt processes, destroy window."""
        if self._tray_icon:
            self._tray_icon.stop()
        # Clean up all running tunnel processes
        try:
            NewtManager.get().stop_all()
        except Exception:
            pass
        self.after(0, self._do_quit)

    def _do_quit(self):
        if self.current_frame:
            self.current_frame.destroy()
        self.destroy()

    # ── Session / routing ────────────────────────────────────────

    def _validate_session(self):
        def worker():
            me = self.api.get_me()
            if me:
                self.after(0, self._show_dashboard)
            else:
                self.api.logout()
                self.after(0, self._show_login)
        threading.Thread(target=worker, daemon=True).start()

    def _show_login(self):
        if self.current_frame:
            self.current_frame.destroy()
        self.current_frame = LoginFrame(self, self.api, self._show_dashboard)
        self.current_frame.pack(fill="both", expand=True)

    def _show_dashboard(self):
        if self.current_frame:
            self.current_frame.destroy()
        self.current_frame = DashboardFrame(self, self.api, self._show_login)
        self.current_frame.pack(fill="both", expand=True)
        # Check for updates after showing dashboard
        self._check_for_update()
        # Handle deep link — auto-connect tunnel
        if self._deep_link:
            dl = self._deep_link
            self._deep_link = None  # consume it once
            self.after(500, lambda: self._handle_deep_link_connect(dl))

    def _check_for_update(self):
        """Background check for a new version — shows dialog if available."""
        def worker():
            info = self.api.check_for_update()
            if info:
                self.after(0, lambda: self._show_update_dialog(info))
        threading.Thread(target=worker, daemon=True).start()

    def _handle_deep_link_connect(self, dl: dict):
        """Handle a dynoip://connect deep link — switch to Tunnels tab and start tunnel."""
        dashboard = self.current_frame
        if not isinstance(dashboard, DashboardFrame):
            return

        # Switch to the Tunnels tab
        dashboard.tab_view.set("  Tunnels  ")

        endpoint = dl["endpoint"]
        newt_id = dl["newt_id"]
        newt_secret = dl["newt_secret"]

        # Use a pseudo tunnel_id based on hash (deep links don't have a DB id)
        tunnel_id = hash(newt_id) & 0x7FFFFFFF

        def _connect():
            mgr = NewtManager.get()
            success = mgr.start(
                tunnel_id=tunnel_id,
                name=f"deeplink-{newt_id[:8]}",
                endpoint=endpoint,
                newt_id=newt_id,
                newt_secret=newt_secret,
                log_cb=lambda msg, lvl: log.info("[deeplink] %s", msg),
            )
            status = "Connected!" if success else "Failed to connect"
            self.after(0, lambda: self._show_deep_link_status(status, success))

        threading.Thread(target=_connect, daemon=True).start()

    def _show_deep_link_status(self, message: str, success: bool):
        """Brief toast showing deep link connection result."""
        color = C_SUCCESS if success else C_ERROR
        dialog = ctk.CTkToplevel(self)
        dialog.title("Tunnel Connection")
        dialog.geometry("340x100")
        dialog.configure(fg_color=C_BG)
        dialog.transient(self)
        dialog.resizable(False, False)
        dialog.update_idletasks()
        x = self.winfo_x() + (self.winfo_width() - 340) // 2
        y = self.winfo_y() + (self.winfo_height() - 100) // 2
        dialog.geometry(f"+{x}+{y}")

        ctk.CTkLabel(dialog, text=message, font=("Segoe UI", 15, "bold"),
                     text_color=color).pack(expand=True, pady=(20, 5))
        ctk.CTkButton(dialog, text="OK", width=80, fg_color=C_ACCENT,
                      hover_color="#00b8d4", text_color="#000",
                      command=dialog.destroy).pack(pady=(0, 15))
        # Auto-close after 5 seconds
        dialog.after(5000, lambda: dialog.destroy() if dialog.winfo_exists() else None)

    def _show_update_dialog(self, info: dict):
        """Show a non-blocking update notification dialog."""
        version = info.get("version", "?")
        url = info.get("download_url", "")
        notes = info.get("release_notes", "")
        mandatory = info.get("is_mandatory", False)

        dialog = ctk.CTkToplevel(self)
        dialog.title("Update Available")
        dialog.geometry("440x320")
        dialog.configure(fg_color=C_BG)
        dialog.transient(self)
        dialog.grab_set()
        dialog.resizable(False, False)

        # Center on parent
        dialog.update_idletasks()
        x = self.winfo_x() + (self.winfo_width() - 440) // 2
        y = self.winfo_y() + (self.winfo_height() - 320) // 2
        dialog.geometry(f"+{x}+{y}")

        frame = ctk.CTkFrame(dialog, fg_color=C_BG_CARD, corner_radius=12)
        frame.pack(fill="both", expand=True, padx=16, pady=16)

        ctk.CTkLabel(frame, text="🔄  Update Available", font=("Segoe UI", 18, "bold"),
                     text_color=C_ACCENT).pack(pady=(16, 4))

        ctk.CTkLabel(frame, text=f"v{APP_VERSION}  →  v{version}",
                     font=("Segoe UI", 14), text_color=C_TEXT).pack(pady=(0, 8))

        if notes:
            notes_box = ctk.CTkTextbox(frame, height=80, fg_color=C_BG_DARKER,
                                       text_color=C_TEXT_DIM, corner_radius=8,
                                       font=("Segoe UI", 11), wrap="word")
            notes_box.pack(fill="x", padx=16, pady=(0, 8))
            notes_box.insert("1.0", notes)
            notes_box.configure(state="disabled")

        if mandatory:
            ctk.CTkLabel(frame, text="⚠  This update is required",
                         font=("Segoe UI", 11, "bold"), text_color=C_WARNING).pack(pady=(0, 8))

        btn_frame = ctk.CTkFrame(frame, fg_color="transparent")
        btn_frame.pack(fill="x", padx=16, pady=(4, 16))

        status_label = ctk.CTkLabel(btn_frame, text="", font=("Segoe UI", 11),
                                    text_color=C_TEXT_DIM)
        status_label.pack(pady=(0, 6))

        progress = ctk.CTkProgressBar(btn_frame, fg_color=C_BG_DARKER,
                                      progress_color=C_ACCENT, height=6)

        def do_download():
            """Download the installer and run it."""
            download_btn.configure(state="disabled", text="Downloading...")
            progress.pack(fill="x", pady=(0, 8))
            progress.set(0)
            status_label.configure(text="Downloading update...")

            def dl_worker():
                try:
                    tmp_dir = os.path.join(os.environ.get("TEMP", CONFIG_DIR), "DynoIP_Update")
                    os.makedirs(tmp_dir, exist_ok=True)
                    filename = url.split("/")[-1] if "/" in url else "DynoIP-Setup.exe"
                    dest = os.path.join(tmp_dir, filename)

                    r = requests.get(url, stream=True, timeout=120)
                    r.raise_for_status()
                    total = int(r.headers.get("content-length", 0))
                    downloaded = 0
                    with open(dest, "wb") as f:
                        for chunk in r.iter_content(8192):
                            f.write(chunk)
                            downloaded += len(chunk)
                            if total > 0:
                                self.after(0, lambda d=downloaded, t=total: progress.set(d / t))

                    self.after(0, lambda: status_label.configure(text="Launching installer..."))
                    # Launch the installer and close the app
                    subprocess.Popen([dest], creationflags=0x00000008)  # DETACHED_PROCESS
                    self.after(500, lambda: self._quit_app())
                except Exception as e:
                    self.after(0, lambda: status_label.configure(
                        text=f"Download failed: {e}", text_color=C_ERROR))
                    self.after(0, lambda: download_btn.configure(state="normal", text="Retry"))

            threading.Thread(target=dl_worker, daemon=True).start()

        download_btn = ctk.CTkButton(
            btn_frame, text="Download & Install", fg_color=C_ACCENT,
            hover_color="#00b8d4", text_color="#000",
            font=("Segoe UI", 13, "bold"), height=36,
            command=do_download
        )
        download_btn.pack(side="left", expand=True, fill="x", padx=(0, 4))

        if not mandatory:
            ctk.CTkButton(
                btn_frame, text="Later", fg_color=C_BG_DARKER,
                hover_color=C_BORDER, text_color=C_TEXT_DIM,
                font=("Segoe UI", 13), height=36,
                command=dialog.destroy
            ).pack(side="left", expand=True, fill="x", padx=(4, 0))


# ═══════════════════════════════════════════════════════════════════
# ENTRY POINT
# ═══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    # Register protocol handler on every launch (idempotent, fast)
    register_protocol_handler()

    # Check for OAuth callback deep link (dynoip://auth?access_token=...&refresh_token=...)
    # If found, write tokens for the running instance and exit immediately.
    for arg in sys.argv[1:]:
        oauth_tokens = parse_oauth_deep_link(arg)
        if oauth_tokens:
            _write_oauth_callback(oauth_tokens)
            sys.exit(0)

    # Check for tunnel deep link URL (dynoip://connect?endpoint=...&id=...&secret=...)
    deep_link = None
    for arg in sys.argv[1:]:
        deep_link = parse_deep_link(arg)
        if deep_link:
            break

    app = DynoIPApp(deep_link=deep_link)
    app.mainloop()
