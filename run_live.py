"""Production server for 24/7 live use (office network or behind Cloudflare Tunnel).

Run: python run_live.py
Uses Waitress WSGI — stable for team access, not the Flask debug server.
"""

from __future__ import annotations

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
os.chdir(HERE)
sys.path.insert(0, HERE)


def _config() -> dict:
    try:
        with open(os.path.join(HERE, "config.json"), "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, json.JSONDecodeError):
        return {}


def main() -> None:
    cfg = _config()
    srv = cfg.get("server", {})
    host = srv.get("host", "0.0.0.0")
    port = int(srv.get("port", 5000))
    threads = int(srv.get("threads", 8))

    import web  # noqa: WPS433 — loads Flask app + DB migrate

    from waitress import serve

    print("=" * 60)
    print("  FSS Invoice Tool — LIVE")
    print(f"  Listening on http://{host}:{port}")
    print("  Stop with Ctrl+C (or end the scheduled task)")
    print("=" * 60)
    serve(web.app, host=host, port=port, threads=threads)


if __name__ == "__main__":
    main()
