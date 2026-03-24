"""Dyno-IP Dynamic DNS client — zero-dependency DDNS updater."""

__version__ = "2.6.0"

from dynoip.core import update_ip, run_once, daemon_loop  # noqa: F401
