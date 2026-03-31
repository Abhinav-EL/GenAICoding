import importlib
import sys
import threading
from pathlib import Path

import pytest


class DummyThread:
    def __init__(self, *args, **kwargs):
        pass

    def start(self):
        pass


def import_user_flask_app(monkeypatch):
    root = Path(__file__).resolve().parent.parent
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    monkeypatch.setattr(threading, "Thread", DummyThread)

    import userFlaskApp
    importlib.reload(userFlaskApp)

    with userFlaskApp.app.app_context():
        userFlaskApp.db.drop_all()
        userFlaskApp.db.create_all()

    return userFlaskApp


def test_import_does_not_start_an_actual_http_server(monkeypatch):
    module = import_user_flask_app(monkeypatch)
    assert hasattr(module, "app")
    assert module.app.name == "userFlaskApp"


def test_add_user_with_invalid_json_returns_400(monkeypatch):
    module = import_user_flask_app(monkeypatch)
    client = module.app.test_client()

    resp = client.post("/user", data="not-json", content_type="application/json")
    assert resp.status_code == 400

    resp = client.post("/user", json=None)
    assert resp.status_code == 415


def test_add_user_rejects_short_password(monkeypatch):
    module = import_user_flask_app(monkeypatch)
    client = module.app.test_client()

    payload = {"username": "attacker", "password": "123"}
    resp = client.post("/user", json=payload)

    assert resp.status_code == 400
    assert "password" in resp.get_json()


def test_user_creation_stores_hashed_password(monkeypatch):
    module = import_user_flask_app(monkeypatch)
    client = module.app.test_client()

    payload = {"username": "alice", "password": "SuperSecret123"}
    resp = client.post("/user", json=payload)
    assert resp.status_code == 201

    user_resp = client.get("/user/1")
    assert user_resp.status_code == 200
    returned = user_resp.get_json()

    assert returned["username"] == "alice"
    assert returned["password"] != payload["password"]
    assert ":" in returned["password"]


def test_user_list_exposes_password_hash(monkeypatch):
    module = import_user_flask_app(monkeypatch)
    client = module.app.test_client()

    client.post("/user", json={"username": "bob", "password": "AnotherSecret1"})
    resp = client.get("/users")

    assert resp.status_code == 200
    users = resp.get_json()
    assert isinstance(users, list)
    assert len(users) == 1
    assert "password" in users[0]
    assert users[0]["password"] != "AnotherSecret1"


def test_duplicate_username_causes_server_error(monkeypatch):
    module = import_user_flask_app(monkeypatch)
    client = module.app.test_client()

    payload = {"username": "charlie", "password": "ValidPass123"}
    resp1 = client.post("/user", json=payload)
    assert resp1.status_code == 201

    resp2 = client.post("/user", json=payload)
    assert resp2.status_code == 500


def test_sql_like_username_does_not_crash(monkeypatch):
    module = import_user_flask_app(monkeypatch)
    client = module.app.test_client()

    payload = {"username": "Robert'); DROP TABLE users; --", "password": "ValidPass123"}
    resp = client.post("/user", json=payload)
    assert resp.status_code in (201, 400)
    assert resp.status_code != 500
