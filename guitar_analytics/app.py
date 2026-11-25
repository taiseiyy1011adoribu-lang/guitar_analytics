"""ダブルクリックで起動するアプリの入口（Windows の exe もここから作る）。

ローカルの画面（guitar_analytics.web）を起動して、ブラウザで開く。
すでに起動していれば、新しく起動せずにその画面をブラウザで開くだけにする。

    python -m guitar_analytics.app
"""
from __future__ import annotations

import os
import sys
import tempfile
import threading
import urllib.request
import webbrowser
from http.server import ThreadingHTTPServer

HOST = "127.0.0.1"
PORT = 8000  # 使用中なら空いているポートを使う
SERVER_NAME = "guitar_analytics"


def _prepare_streams() -> None:
    """コンソールの無い起動方法でも print で落ちないようにする。"""
    log = None
    for name in ("stdout", "stderr"):
        stream = getattr(sys, name)
        if stream is None:
            if log is None:
                path = os.path.join(tempfile.gettempdir(), "guitar_analytics.log")
                log = open(path, "a", encoding="utf-8", buffering=1)
            setattr(sys, name, log)
        elif hasattr(stream, "reconfigure"):
            # Windows のコンソールで日本語が表示できなくても止まらないように
            stream.reconfigure(errors="replace")


def _prepare_env() -> None:
    # librosa が使う numba のキャッシュを書き込める場所に置く
    os.environ.setdefault(
        "NUMBA_CACHE_DIR", os.path.join(tempfile.gettempdir(), "guitar_analytics_numba")
    )


def already_running(url: str) -> bool:
    """url でこのアプリがすでに動いているか。"""
    try:
        with urllib.request.urlopen(url, timeout=1) as res:
            return SERVER_NAME in res.headers.get("Server", "")
    except OSError:
        return False


def make_server(host: str = HOST, port: int = PORT) -> ThreadingHTTPServer:
    """port が使用中なら、OS が選んだ空きポートで作る。"""
    from .web.server import Handler

    try:
        return ThreadingHTTPServer((host, port), Handler)
    except OSError:
        return ThreadingHTTPServer((host, 0), Handler)


def _warm_up() -> None:
    """最初の解析が遅くならないよう、重いライブラリを先に読み込んでおく。"""
    try:
        import basic_pitch.inference  # noqa: F401
        import librosa  # noqa: F401
    except Exception:  # 読み込みの失敗は解析時に画面へ出るので、ここでは無視する
        pass


def main(argv: list[str] | None = None) -> int:
    _prepare_streams()
    _prepare_env()
    args = sys.argv[1:] if argv is None else argv
    open_browser = "--no-browser" not in args

    default_url = f"http://{HOST}:{PORT}/"
    if already_running(default_url):
        print("すでに起動しています。ブラウザで画面を開きます。")
        if open_browser:
            webbrowser.open(default_url)
        return 0

    httpd = make_server()
    url = f"http://{HOST}:{httpd.server_address[1]}/"
    print("ギターのタブ譜アプリを起動しました。")
    print(f"ブラウザで {url} を開いています。開かないときはこのアドレスを貼り付けてください。")
    print("この黒い画面を閉じると、アプリが終了します。")
    threading.Thread(target=_warm_up, daemon=True).start()
    if open_browser:
        threading.Timer(0.5, webbrowser.open, args=(url,)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
