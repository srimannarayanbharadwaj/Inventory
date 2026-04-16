from __future__ import annotations

import socket
import subprocess
import sys
import time
import urllib.request
import webbrowser
from pathlib import Path


APP_DIR = Path(__file__).resolve().parent
PROJECT_ROOT_VENV = APP_DIR.parent / ".venv" / "Scripts" / "python.exe"
LOCAL_VENV = APP_DIR / ".venv" / "Scripts" / "python.exe"
IDLE_TIMEOUT_SECONDS = 20
PORT_START = 8501
PORT_END = 8510
PID_FILE = APP_DIR / ".inventory_server.json"


def _win_hidden_kwargs() -> dict:
    if sys.platform != "win32":
        return {}
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startupinfo.wShowWindow = 0  # SW_HIDE
    return {"startupinfo": startupinfo, "creationflags": subprocess.CREATE_NO_WINDOW}


def is_port_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.2)
        return s.connect_ex(("127.0.0.1", port)) != 0


def choose_port() -> int:
    for port in range(PORT_START, PORT_END + 1):
        if is_port_free(port):
            return port
    return PORT_START


def has_established_connections(port: int) -> bool:
    try:
        out = subprocess.check_output(
            ["netstat", "-na"],
            text=True,
            encoding="utf-8",
            errors="ignore",
            **_win_hidden_kwargs(),
        )
    except Exception:
        return True
    needle = f":{port}"
    for line in out.splitlines():
        u = line.upper()
        if needle in line and "ESTABLISHED" in u:
            return True
    return False


def preferred_python_executable() -> str:
    if PROJECT_ROOT_VENV.exists():
        return str(PROJECT_ROOT_VENV)
    if LOCAL_VENV.exists():
        return str(LOCAL_VENV)
    return sys.executable


def wait_for_streamlit_ready(url: str, timeout_seconds: int = 25) -> bool:
    health_url = f"{url}/_stcore/health"
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(health_url, timeout=1) as response:
                body = response.read().decode("utf-8", errors="ignore").strip().lower()
                if response.status == 200 and body == "ok":
                    return True
        except Exception:
            pass
        time.sleep(0.5)
    return False


def main() -> int:
    port = choose_port()
    url = f"http://localhost:{port}"
    print(f"Opening browser at {url}")

    cmd = [
        preferred_python_executable(),
        "-m",
        "streamlit",
        "run",
        str(APP_DIR / "app.py"),
        "--server.port",
        str(port),
        "--server.headless",
        "true",
    ]
    proc = subprocess.Popen(cmd, cwd=str(APP_DIR), **_win_hidden_kwargs())
    try:
        PID_FILE.write_text(f'{{"pid": {proc.pid}, "port": {port}}}', encoding="utf-8")
    except Exception:
        pass

    # Wait for Streamlit to be ready before opening the browser.
    wait_for_streamlit_ready(url)
    webbrowser.open(url)

    # Do not instantly stop before a user gets the first page load.
    startup_grace = time.time() + 12
    last_seen_active = time.time()

    try:
        while proc.poll() is None:
            active = has_established_connections(port)
            now = time.time()
            if active:
                last_seen_active = now
            elif now > startup_grace and (now - last_seen_active) >= IDLE_TIMEOUT_SECONDS:
                print("No active browser tab detected. Stopping app...")
                proc.terminate()
                break
            time.sleep(2)
    except KeyboardInterrupt:
        pass
    finally:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
        try:
            if PID_FILE.exists():
                PID_FILE.unlink()
        except Exception:
            pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

