import base64
import json
import threading
import urllib.error
import urllib.request

import pytest

from care_voice.dashboard import PASSWORD_ENV, render_alerts, render_checkins, serve
from care_voice.risk import RiskEngine
from care_voice.store import Store


@pytest.fixture
def store(run_session):
    store = Store(":memory:")
    result = run_session(["yes", "no <script>", "yes", "no", "no", "wednesday", "4"])
    store.save_checkin(result)
    store.save_alerts(RiskEngine().evaluate(result))
    return store


@pytest.fixture
def running(store):
    servers = []

    def start():
        server = serve(store, "127.0.0.1", 0)
        threading.Thread(target=server.serve_forever, args=(0.05,), daemon=True).start()
        servers.append(server)
        return f"http://127.0.0.1:{server.server_address[1]}"

    yield start
    for server in servers:
        server.shutdown()
        server.server_close()


def get(url, auth=None):
    req = urllib.request.Request(url)
    if auth:
        req.add_header("Authorization", "Basic " + base64.b64encode(auth.encode()).decode())
    with urllib.request.urlopen(req, timeout=5) as resp:
        return resp.status, resp.headers.get("Content-Type"), resp.read().decode()


def test_dashboard_pages(running):
    base = running()
    status, ctype, page = get(base + "/")
    assert status == 200 and ctype.startswith("text/html")
    assert "MISSED_MEDS" in page
    assert "Not a medical device" in page
    assert "<script>" not in page and "&lt;script&gt;" in page

    _, ctype, body = get(base + "/api/checkins")
    (checkin,) = json.loads(body)
    assert checkin["answers"]["took_meds"]["value"] is False
    _, _, body = get(base + "/api/alerts")
    assert json.loads(body)[0]["code"] == "MISSED_MEDS"
    assert get(base + "/healthz")[2] == "ok"
    with pytest.raises(urllib.error.HTTPError) as exc:
        get(base + "/nope")
    assert exc.value.code == 404
    req = urllib.request.Request(base + "/twilio/voice", data=b"", method="POST")
    with pytest.raises(urllib.error.HTTPError) as exc:
        urllib.request.urlopen(req, timeout=5)
    assert exc.value.code == 404


def test_password_protection(monkeypatch, running):
    monkeypatch.setenv(PASSWORD_ENV, "hunter2")
    base = running()
    assert get(base + "/healthz")[2] == "ok"
    for auth in (None, "x:wrong", "garbage-no-colon"):
        with pytest.raises(urllib.error.HTTPError) as exc:
            get(base + "/", auth)
        assert exc.value.code == 401
    req = urllib.request.Request(base + "/", headers={"Authorization": "Basic !!!"})
    with pytest.raises(urllib.error.HTTPError):
        urllib.request.urlopen(req, timeout=5)
    assert get(base + "/", "anyone:hunter2")[0] == 200


def test_empty_states():
    assert "No alerts yet" in render_alerts([])
    assert "care-voice simulate" in render_checkins([])
