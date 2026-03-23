"""
Dyno-IP DDNS Update Service — Windows Service (.exe)

Runs as a native Windows service via pywin32.
Configuration stored in: C:\\ProgramData\\DynoIP\\config.ini

Build:
    pip install pywin32 pyinstaller
    pyinstaller --onefile --name dynoip-service --hidden-import win32timezone dynoip_win_service.py

Install/Manage (elevated cmd):
    dynoip-service.exe install
    dynoip-service.exe start
    dynoip-service.exe stop
    dynoip-service.exe remove

Or use the included installer:
    dynoip-installer.bat
"""

import os
import sys
import configparser
import logging
import threading

import win32serviceutil
import win32service
import win32event
import servicemanager

# Add our directory to path so we can import dynoip_core
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dynoip_core import daemon_loop, run_once, __version__

# ── Constants ──
SERVICE_NAME = "DynoIPUpdate"
SERVICE_DISPLAY = "Dyno-IP Dynamic DNS Updater"
SERVICE_DESC = "Automatically updates your Dyno-IP dynamic DNS record when your IP changes."
CONFIG_DIR = os.path.join(os.environ.get("PROGRAMDATA", r"C:\ProgramData"), "DynoIP")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.ini")
LOG_FILE = os.path.join(CONFIG_DIR, "dynoip.log")


def ensure_config():
    """Create default config file if it doesn't exist."""
    os.makedirs(CONFIG_DIR, exist_ok=True)
    if not os.path.exists(CONFIG_FILE):
        config = configparser.ConfigParser()
        config["dynoip"] = {
            "token": "YOUR_UPDATE_TOKEN_HERE",
            "api_url": "https://dyno-ip.com/api/ip/update",
            "interval": "300",
        }
        with open(CONFIG_FILE, "w") as f:
            config.write(f)
    return CONFIG_FILE


def read_config():
    """Read configuration from config.ini."""
    ensure_config()
    config = configparser.ConfigParser()
    config.read(CONFIG_FILE, encoding="utf-8-sig")  # utf-8-sig handles optional BOM
    section = config["dynoip"] if "dynoip" in config else {}
    return {
        "token": section.get("token", "YOUR_UPDATE_TOKEN_HERE"),
        "api_url": section.get("api_url", "https://dyno-ip.com/api/ip/update"),
        "interval": int(section.get("interval", "300")),
    }


def setup_logging():
    """Configure logging to file."""
    os.makedirs(CONFIG_DIR, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[
            logging.FileHandler(LOG_FILE, encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )


class DynoIPService(win32serviceutil.ServiceFramework):
    _svc_name_ = SERVICE_NAME
    _svc_display_name_ = SERVICE_DISPLAY
    _svc_description_ = SERVICE_DESC

    def __init__(self, args):
        win32serviceutil.ServiceFramework.__init__(self, args)
        self.stop_event = threading.Event()
        self.hWaitStop = win32event.CreateEvent(None, 0, 0, None)

    def SvcStop(self):
        """Called when the service is asked to stop."""
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        self.stop_event.set()
        win32event.SetEvent(self.hWaitStop)

    def SvcDoRun(self):
        """Main service entry point."""
        servicemanager.LogMsg(
            servicemanager.EVENTLOG_INFORMATION_TYPE,
            servicemanager.PYS_SERVICE_STARTED,
            (self._svc_name_, ""),
        )
        setup_logging()
        log = logging.getLogger("dynoip")
        log.info("Dyno-IP service v%s starting", __version__)

        cfg = read_config()
        if cfg["token"] == "YOUR_UPDATE_TOKEN_HERE":
            log.error(
                "Token not configured! Edit %s and set your update token, then restart the service.",
                CONFIG_FILE,
            )
            # Keep service running but log the error every 60s so it's visible
            while not self.stop_event.is_set():
                self.stop_event.wait(60)
            return

        log.info("Config: interval=%ds, api=%s", cfg["interval"], cfg["api_url"])
        daemon_loop(
            token=cfg["token"],
            interval=cfg["interval"],
            api_url=cfg["api_url"],
            stop_event=self.stop_event,
        )
        log.info("Dyno-IP service stopped")


# ── CLI for interactive use ──
def cli_main():
    """Handle command-line arguments for non-service use."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Dyno-IP DDNS Windows Service",
        epilog="Service commands: install, start, stop, remove, restart, debug",
    )
    parser.add_argument("--configure", action="store_true", help="Open config file for editing")
    parser.add_argument("--test", action="store_true", help="Run a single update test")
    parser.add_argument("--status", action="store_true", help="Show service status")
    parser.add_argument("--version", action="version", version=f"Dyno-IP Client v{__version__}")

    # If we have service commands, defer to win32serviceutil
    if len(sys.argv) > 1 and sys.argv[1] in ("install", "start", "stop", "remove", "restart", "debug", "update"):
        ensure_config()
        win32serviceutil.HandleCommandLine(DynoIPService)
        return

    args, remaining = parser.parse_known_args()

    if args.configure:
        path = ensure_config()
        print(f"Config file: {path}")
        os.startfile(path)
        return

    if args.test:
        setup_logging()
        cfg = read_config()
        if cfg["token"] == "YOUR_UPDATE_TOKEN_HERE":
            print(f"ERROR: Edit {CONFIG_FILE} and set your update token first.")
            sys.exit(1)
        print(f"Testing update with token {cfg['token'][:8]}...")
        success = run_once(cfg["token"], api_url=cfg["api_url"])
        sys.exit(0 if success else 1)

    if args.status:
        try:
            import win32service as ws
            scm = ws.OpenSCManager(None, None, ws.SC_MANAGER_CONNECT)
            try:
                svc = ws.OpenService(scm, SERVICE_NAME, ws.SERVICE_QUERY_STATUS)
                status = ws.QueryServiceStatus(svc)
                state_map = {
                    ws.SERVICE_STOPPED: "STOPPED",
                    ws.SERVICE_START_PENDING: "STARTING",
                    ws.SERVICE_STOP_PENDING: "STOPPING",
                    ws.SERVICE_RUNNING: "RUNNING",
                    ws.SERVICE_CONTINUE_PENDING: "RESUMING",
                    ws.SERVICE_PAUSE_PENDING: "PAUSING",
                    ws.SERVICE_PAUSED: "PAUSED",
                }
                print(f"Service: {SERVICE_DISPLAY}")
                print(f"Status:  {state_map.get(status[1], 'UNKNOWN')}")
                print(f"Config:  {CONFIG_FILE}")
                print(f"Log:     {LOG_FILE}")
                ws.CloseServiceHandle(svc)
            except Exception:
                print(f"Service '{SERVICE_NAME}' is not installed.")
                print(f"Install with: dynoip-service.exe install")
            ws.CloseServiceHandle(scm)
        except ImportError:
            print("Cannot query service status (pywin32 required)")
        return

    # No args — show help
    parser.print_help()
    print(f"\nConfig: {CONFIG_FILE}")
    print(f"Log:    {LOG_FILE}")


if __name__ == "__main__":
    # Detect if running as a service or interactively
    if len(sys.argv) == 1:
        # Could be service start or interactive — try service first
        try:
            servicemanager.Initialize()
            servicemanager.PrepareToHostSingle(DynoIPService)
            servicemanager.StartServiceCtrlDispatcher()
        except Exception:
            # Not running as service — show CLI help
            cli_main()
    else:
        cli_main()
