import json
import threading
import urllib.request
from http.server import ThreadingHTTPServer

from guitar_analytics.transcribe import Note
from guitar_analytics.web import server
from guitar_analytics.web.analyze import Options, build_result


def test_build_result_links_events_to_notes():
    notes = [
        Note(0.0, 0.5, 52, 0.8),
        Note(0.0, 0.4, 64, 0.3),  # 52 のオクターブ上で弱いので倍音として除かれる
        Note(0.01, 0.6, 56, 0.7),
        Note(1.0, 1.5, 64, 0.9),
    ]
    r = build_result(notes, Options())
    assert r["duration"] == 1.5
    assert [n["dropped"] for n in r["notes"]] == [False, True, False, False]
    assert [e["time"] for e in r["events"]] == [0.0, 1.0]
    first = {n["pitch"]: n for n in r["events"][0]["notes"]}
    assert set(first) == {52, 56}
    assert first[56]["end"] == 0.6 and first[56]["velocity"] == 0.7
    assert all(n["string"] in range(1, 7) for e in r["events"] for n in e["notes"])
    assert r["ascii"].count("|") == 12


def test_options_from_query():
    o = Options.from_query({"onset_threshold": ["0.4"], "keep_harmonics": ["1"]})
    assert o.onset_threshold == 0.4 and o.keep_harmonics and o.chord_ms == 50.0


def _serve():
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, f"http://127.0.0.1:{httpd.server_address[1]}"


def test_server_serves_page_and_rejects_bad_upload(monkeypatch):
    httpd, base = _serve()
    try:
        html = urllib.request.urlopen(base + "/").read().decode()
        assert "タブ譜ビューア" in html

        monkeypatch.setattr(server, "analyze", lambda path, opts: {"ok": path.suffix})
        req = urllib.request.Request(base + "/api/analyze?name=a.wav", data=b"RIFF", method="POST")
        assert json.load(urllib.request.urlopen(req)) == {"ok": ".wav"}

        bad = urllib.request.Request(base + "/api/analyze?name=a.exe", data=b"x", method="POST")
        try:
            urllib.request.urlopen(bad)
            raise AssertionError("should fail")
        except urllib.error.HTTPError as e:
            assert e.code == 400
        try:
            urllib.request.urlopen(base + "/../pyproject.toml")
            raise AssertionError("should fail")
        except urllib.error.HTTPError as e:
            assert e.code == 404
    finally:
        httpd.shutdown()
