from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


APP_DIR = Path(__file__).resolve().parent
PID_FILE = APP_DIR / ".inventory_server.json"


def _win_hidden_kwargs() -> dict:
    if sys.platform != "win32":
        return {}
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startupinfo.wShowWindow = 0  # SW_HIDE
    return {"startupinfo": startupinfo, "creationflags": subprocess.CREATE_NO_WINDOW}


def main() -> int:
    if not PID_FILE.exists():
        return 0

    try:
        data = json.loads(PID_FILE.read_text(encoding="utf-8"))
        pid = int(data.get("pid"))
    except Exception:
        pid = None

    try:
        PID_FILE.unlink(missing_ok=True)  # type: ignore[arg-type]
    except Exception:
        pass

    if not pid:
        return 0

    if sys.platform == "win32":
        # Kill process tree (Streamlit spawns child processes sometimes)
        subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], **_win_hidden_kwargs())
        return 0

    try:
        subprocess.run(["kill", "-TERM", str(pid)], check=False)
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

