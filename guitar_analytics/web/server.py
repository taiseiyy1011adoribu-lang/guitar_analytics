"""標準ライブラリだけで動くローカルサーバー。

GET  /              画面（static/index.html）
POST /api/analyze   音声ファイルをそのまま本文で受け取り、解析結果を JSON で返す
                    しきい値はクエリ文字列で渡す（例: ?onset_threshold=0.4）
"""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
import threading
import traceback
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .analyze import Options, analyze

STATIC = Path(__file__).with_name("static")
MAX_UPLOAD = 200 * 1024 * 1024  # 200MB
ALLOWED_SUFFIXES = {".wav", ".mp3", ".flac", ".ogg", ".m4a", ".aiff", ".aif"}
CONTENT_TYPES = {".html": "text/html; charset=utf-8", ".js": "text/javascript", ".css": "text/css"}

# TensorFlow を複数スレッドから同時に呼ばないよう解析は 1 つずつ
_analyze_lock = threading.Lock()


class Handler(BaseHTTPRequestHandler):
    server_version = "guitar_analytics"

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        name = "index.html" if path in ("/", "/index.html") else path.lstrip("/")
        file = (STATIC / name).resolve()
        if STATIC.resolve() not in file.parents or not file.is_file():
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        body = file.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", CONTENT_TYPES.get(file.suffix, "application/octet-stream"))
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:  # noqa: N802
        url = urlparse(self.path)
        if url.path != "/api/analyze":
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        length = int(self.headers.get("Content-Length") or 0)
        if not 0 < length <= MAX_UPLOAD:
            self._json(HTTPStatus.BAD_REQUEST, {"error": "ファイルが空か、大きすぎます"})
            return
        query = parse_qs(url.query)
        suffix = Path(query.get("name", ["audio.wav"])[0]).suffix.lower() or ".wav"
        if suffix not in ALLOWED_SUFFIXES:
            self._json(HTTPStatus.BAD_REQUEST, {"error": f"対応していない形式です: {suffix}"})
            return
        try:
            opts = Options.from_query(query)
        except ValueError:
            self._json(HTTPStatus.BAD_REQUEST, {"error": "しきい値の値が不正です"})
            return

        data = self.rfile.read(length)
        with tempfile.TemporaryDirectory() as tmp:
            audio = Path(tmp) / f"upload{suffix}"
            audio.write_bytes(data)
            try:
                with _analyze_lock:
                    result = analyze(audio, opts)
            except Exception as exc:  # 解析の失敗は画面に出す
                traceback.print_exc()
                self._json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": f"解析に失敗しました: {exc}"})
                return
        self._json(HTTPStatus.OK, result)

    def _json(self, status: HTTPStatus, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt: str, *args) -> None:
        sys.stderr.write(f"[web] {fmt % args}\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="guitar_analytics.web", description="タブ譜をブラウザで見るためのローカル画面"
    )
    parser.add_argument("--host", default="127.0.0.1", help="待ち受けるアドレス")
    parser.add_argument("--port", type=int, default=8000, help="ポート番号")
    parser.add_argument("--no-browser", action="store_true", help="ブラウザを自動で開かない")
    args = parser.parse_args(argv)

    httpd = ThreadingHTTPServer((args.host, args.port), Handler)
    url = f"http://{args.host}:{args.port}/"
    print(f"{url} で待ち受けています（Ctrl+C で終了）", file=sys.stderr)
    if not args.no_browser:
        threading.Timer(0.5, webbrowser.open, args=(url,)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
    return 0
