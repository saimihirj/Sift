"""Single-process launcher for Sift."""

from __future__ import annotations

import argparse
import os
import socket
import subprocess
import time
import webbrowser
from pathlib import Path
from shutil import which
from urllib.parse import urlparse
from urllib.request import urlopen

import uvicorn

try:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parent / ".env")
except ImportError:  # pragma: no cover - optional dependency path
    pass


ROOT = Path(__file__).resolve().parent
FRONTEND_DIST = ROOT / "frontend" / "dist" / "index.html"
OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434")


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


def _should_manage_ollama() -> bool:
    provider_mode = os.environ.get("SIFT_MODEL_PROVIDER", "auto").strip().lower()
    if provider_mode not in {"", "auto", "ollama"}:
        return False
    parsed = urlparse(OLLAMA_BASE_URL)
    return parsed.hostname in {"127.0.0.1", "localhost", "::1"}


def _ollama_is_ready() -> bool:
    for path in ("/api/version", "/api/tags"):
        try:
            with urlopen(f"{OLLAMA_BASE_URL.rstrip('/')}{path}", timeout=1.5) as response:
                if 200 <= getattr(response, "status", 0) < 300:
                    return True
        except Exception:
            continue
    return False


def ensure_ollama_running() -> subprocess.Popen[str] | None:
    if not _should_manage_ollama() or _ollama_is_ready():
        return None

    ollama_bin = which("ollama")
    if not ollama_bin:
        raise RuntimeError("Ollama is not running and the `ollama` command was not found in PATH.")

    process = subprocess.Popen(
        [ollama_bin, "serve"],
        cwd=ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.STDOUT,
        text=True,
    )

    deadline = time.time() + 15
    while time.time() < deadline:
        if process.poll() is not None:
            break
        if _ollama_is_ready():
            return process
        time.sleep(0.25)

    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
    raise RuntimeError("Sift started Ollama, but it did not become ready in time.")


def cleanup_process(process: subprocess.Popen[str] | None) -> None:
    if process is None or process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def configure_runtime_defaults(no_ollama: bool) -> None:
    if not no_ollama:
        return
    provider_mode = os.environ.get("SIFT_MODEL_PROVIDER", "auto").strip().lower()
    if provider_mode in {"", "auto", "ollama"}:
        os.environ["SIFT_MODEL_PROVIDER"] = "groq"


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Sift as a single local web app.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=7860)
    parser.add_argument("--idle-timeout", type=int, default=90, help="Stop after this many idle seconds once the browser disappears.")
    parser.add_argument("--no-open", action="store_true", help="Do not open a browser window automatically.")
    parser.add_argument("--build", action="store_true", help="Force a frontend build before launch.")
    parser.add_argument("--no-ollama", action="store_true", help="Do not auto-start local Ollama.")
    parser.add_argument("--path", default="/", help="Open the browser to this app path.")
    parser.add_argument("--admin", action="store_true", help="Open the app directly on /admin.")
    args = parser.parse_args()

    configure_runtime_defaults(args.no_ollama)
    ensure_frontend_built(skip_build=not args.build)

    os.environ["SIFT_AUTO_STOP_SECONDS"] = str(args.idle_timeout)
    os.environ["SIFT_ADMIN_MODE"] = "true" if args.admin else "false"

    browser_host = "127.0.0.1" if args.host == "0.0.0.0" else args.host
    open_path = "/admin" if args.admin else args.path
    if not open_path.startswith("/"):
        open_path = f"/{open_path}"
    browser_url = f"http://{browser_host}:{args.port}{open_path}"
    shared_url = f"http://{local_ip()}:{args.port}" if args.host == "0.0.0.0" else browser_url
    ollama_process: subprocess.Popen[str] | None = None

    if not args.no_ollama:
        ollama_process = ensure_ollama_running()

    print(f"Sift running at {browser_url}")
    if args.host == "0.0.0.0":
        print(f"LAN test URL: {shared_url}")
    if ollama_process is not None:
        print("Started Ollama automatically.")
    print(f"Auto-stop: {args.idle_timeout}s after the last browser heartbeat")

    if not args.no_open:
        webbrowser.open(browser_url)

    try:
        uvicorn.run("backend.main:app", host=args.host, port=args.port, reload=False)
    finally:
        cleanup_process(ollama_process)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
