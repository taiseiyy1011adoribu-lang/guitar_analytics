import socket
import threading

from guitar_analytics import app


def test_make_server_falls_back_to_free_port_when_busy():
    busy = socket.socket()
    busy.bind(("127.0.0.1", 0))
    busy.listen()
    port = busy.getsockname()[1]
    try:
        httpd = app.make_server(port=port)
        try:
            assert httpd.server_address[1] not in (0, port)
        finally:
            httpd.server_close()
    finally:
        busy.close()


def test_already_running_detects_own_server():
    httpd = app.make_server(port=0)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        url = f"http://127.0.0.1:{httpd.server_address[1]}/"
        assert app.already_running(url)
    finally:
        httpd.shutdown()
        httpd.server_close()

    free = socket.socket()
    free.bind(("127.0.0.1", 0))
    port = free.getsockname()[1]
    free.close()
    assert not app.already_running(f"http://127.0.0.1:{port}/")
