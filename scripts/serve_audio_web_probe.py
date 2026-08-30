"""Serve a compiled Flutter Web probe and persist its browser callback."""

from __future__ import annotations

import argparse
import json
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse


class ProbeHandler(SimpleHTTPRequestHandler):
    report_path: Path

    def do_GET(self) -> None:  # noqa: N802 - stdlib callback name
        parsed = urlparse(self.path)
        if parsed.path != "/report":
            return super().do_GET()

        query = parse_qs(parsed.query)
        payload = {
            "status": query.get("status", [""])[0],
            "error": query.get("error", [""])[0],
        }
        self.report_path.write_text(
            json.dumps(payload, ensure_ascii=False, sort_keys=True),
            encoding="utf-8",
        )
        self.send_response(204)
        self.end_headers()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--port", default=8080, type=int)
    args = parser.parse_args()

    root = args.root.resolve()
    if not root.is_dir():
        raise SystemExit(f"web root does not exist: {root}")
    ProbeHandler.report_path = args.report.resolve()

    handler = lambda *a, **kw: ProbeHandler(*a, directory=str(root), **kw)  # noqa: E731
    server = ThreadingHTTPServer(("127.0.0.1", args.port), handler)
    print(f"FORGE_AUDIO_SERVER ready=http://127.0.0.1:{args.port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        return 0
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
