"""Launcher for the FSS Invoice Generator app.

Double-clicking the desktop/start-menu shortcut runs this with pythonw.exe
(no console window). It:
  - opens the tool in your default browser, and
  - if the server isn't running yet, starts it first (single instance only).
"""

import json
import os
import socket
import subprocess
import sys
import time
import webbrowser
from threading import Timer

HERE = os.path.dirname(os.path.abspath(__file__))
os.chdir(HERE)
sys.path.insert(0, HERE)


def _config():
    try:
        with open(os.path.join(HERE, "config.json"), "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, json.JSONDecodeError):
        return {}


_cfg = _config().get("server", {})
BIND_HOST = _cfg.get("host", "0.0.0.0")  # 0.0.0.0 = reachable by teammates on LAN
PORT = int(_cfg.get("port", 5000))
URL = f"http://127.0.0.1:{PORT}/"        # always open the local browser on localhost


def server_running() -> bool:
    try:
        with socket.create_connection(("127.0.0.1", PORT), timeout=0.6):
            return True
    except OSError:
        return False


def stop_existing_server() -> None:
    """Stop old server on PORT so code updates are picked up."""
    if sys.platform != "win32":
        return
    try:
        out = subprocess.check_output(
            f'netstat -ano | findstr ":{PORT}" | findstr LISTENING',
            shell=True, text=True, stderr=subprocess.DEVNULL)
        for line in out.splitlines():
            parts = line.split()
            if not parts:
                continue
            pid = parts[-1]
            if pid.isdigit() and int(pid) != os.getpid():
                subprocess.run(
                    ["taskkill", "/F", "/PID", pid],
                    capture_output=True, check=False)
    except (OSError, subprocess.CalledProcessError):
        pass


def main():
    stop_existing_server()
    time.sleep(1.0)

    if server_running():
        webbrowser.open(URL)
        return

    import web  # imported lazily so a quick "open browser" path stays fast

    Timer(1.3, lambda: webbrowser.open(URL)).start()
    try:
        web.app.run(host=BIND_HOST, port=PORT, debug=False, use_reloader=False)
    except OSError:
        # Another instance grabbed the port in the meantime — just open it.
        webbrowser.open(URL)


if __name__ == "__main__":
    main()
