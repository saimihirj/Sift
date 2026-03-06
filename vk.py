"""Single-process launcher for Vishwakarma."""

from __future__ import annotations

import argparse
import os
import socket
import subprocess
import sys
import webbrowser
from pathlib import Path

import uvicorn


ROOT = Path(__file__).resolve().parent
FRONTEND_DIST = ROOT / "frontend" / "dist" / "index.html"


def local_ip() -> str:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("8.8.8.8", 80))
        return sock.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        sock.close()


def ensure_frontend_built(skip_build: bool) -> None:
    if FRONTEND_DIST.exists() and skip_build:
        return
    subprocess.run(
        ["npm", "--prefix", "frontend", "run", "build"],
        cwd=ROOT,
        check=True,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Vishwakarma as a single local web app.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=7860)
    parser.add_argument("--idle-timeout", type=int, default=20, help="Stop after this many idle seconds once the browser disappears.")
    parser.add_argument("--no-open", action="store_true", help="Do not open a browser window automatically.")
    parser.add_argument("--build", action="store_true", help="Force a frontend build before launch.")
    parser.add_argument("--path", default="/", help="Open the browser to this app path.")
    parser.add_argument("--admin", action="store_true", help="Open the app directly on /admin.")
    args = parser.parse_args()

    ensure_frontend_built(skip_build=not args.build)

    os.environ["VK_AUTO_STOP_SECONDS"] = str(args.idle_timeout)

    browser_host = "127.0.0.1" if args.host == "0.0.0.0" else args.host
    open_path = "/admin" if args.admin else args.path
    if not open_path.startswith("/"):
        open_path = f"/{open_path}"
    browser_url = f"http://{browser_host}:{args.port}{open_path}"
    shared_url = f"http://{local_ip()}:{args.port}" if args.host == "0.0.0.0" else browser_url

    print(f"Vishwakarma running at {browser_url}")
    if args.host == "0.0.0.0":
        print(f"LAN test URL: {shared_url}")
    print(f"Auto-stop: {args.idle_timeout}s after the last browser heartbeat")

    if not args.no_open:
        webbrowser.open(browser_url)

    uvicorn.run("backend.main:app", host=args.host, port=args.port, reload=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
