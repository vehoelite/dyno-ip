"""
Dyno-IP CLI — command-line entry point.

Usage:
    dynoip --token YOUR_TOKEN                     # Single update (auto-detect IP)
    dynoip --token YOUR_TOKEN --ip 203.0.113.50   # Set specific IP
    dynoip --token YOUR_TOKEN --daemon             # Run as daemon (every 5 min)
    dynoip --token YOUR_TOKEN --daemon --interval 120

The token can also be set via the DYNOIP_TOKEN environment variable.
"""

import argparse
import logging
import os
import sys

from dynoip.core import run_once, daemon_loop, DEFAULT_API_URL, __version__


def main():
    parser = argparse.ArgumentParser(
        prog="dynoip",
        description="Dyno-IP Dynamic DNS client — keep your hostname updated automatically",
    )
    parser.add_argument(
        "--version", action="version", version=f"dynoip {__version__}"
    )
    parser.add_argument(
        "--token",
        default=os.environ.get("DYNOIP_TOKEN", ""),
        help="Update token (or set DYNOIP_TOKEN env var)",
    )
    parser.add_argument(
        "--ip",
        default="AUTO",
        help="IP address to set (default: auto-detect)",
    )
    parser.add_argument(
        "--daemon",
        action="store_true",
        help="Run continuously in daemon mode",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=300,
        help="Seconds between updates in daemon mode (default: 300)",
    )
    parser.add_argument(
        "--api-url",
        default=DEFAULT_API_URL,
        help="API endpoint URL (default: %(default)s)",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable debug logging",
    )
    args = parser.parse_args()

    # Set up logging
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    if not args.token:
        logging.error(
            "No token provided. Use --token YOUR_TOKEN or set DYNOIP_TOKEN env var.\n"
            "Get your token from https://dyno-ip.com → Dashboard → Subdomains."
        )
        sys.exit(1)

    if args.daemon:
        try:
            daemon_loop(args.token, args.interval, args.api_url)
        except KeyboardInterrupt:
            logging.info("Stopped by user")
    else:
        success = run_once(args.token, args.ip, args.api_url)
        if not success:
            sys.exit(1)


if __name__ == "__main__":
    main()
