"""One switched-off site must not hold up the sync of the others.

While KLM was powered down (2026-09-29) every request of a user edit spent
30 s failing to connect to it and came back marked failed, although SHV, SVR
and ERG had been updated within a second. To the operator that read as
"nothing syncs while one site is down".
"""

import requests

from core import admin_sync, proxima_client, vpn_user_sync
from core.proxima_client import SiteGate

SHV = {"id": 2, "name": "SHV", "url": "http://shv", "api_token_enc": "x"}
SVR = {"id": 4, "name": "SVR", "url": "http://svr", "api_token_enc": "x"}
KLM = {"id": 6, "name": "KLM", "url": "http://klm", "api_token_enc": "x"}


class _Resp:
    def __init__(self, status=200, data=None, error=None):
        self.status_code = status
        self._body = {"ok": error is None, "data": data, "error": error}

    def json(self):
        return self._body


class _Wire:
    """Stands in for the network: KLM never answers, the rest do."""

    def __init__(self, dead=("http://klm",)):
        self.dead = set(dead)
        self.calls = []
        self.next_id = 100

    def __call__(self, server, method, path, body=None, timeout=None):
        self.calls.append((server["name"], method, path, timeout))
        if server["url"] in self.dead:
            raise requests.exceptions.ConnectTimeout()
        if method == "GET":
            return _Resp(data=[])
        if method == "POST":
            self.next_id += 1
            return _Resp(data={"id": self.next_id})
        return _Resp(data={})

    def to(self, name):
        return [c for c in self.calls if c[0] == name]


def _row(row_id, username, server, status="pending", remote=None, user_id=None):
    return {
        "id": row_id, "user_id": user_id or row_id, "vpn_server_id": server["id"],
        "server_name": server["name"], "username": username,
        "sync_status": status, "remote_user_id": remote, "sync_error": None,
        "password_hash": "h", "password_changed_at": 10, "password_synced_at": 0,
        "user_enabled": 1, "enabled": 1, "max_peers": 3, "bandwidth_quota": 0,
        "speed_download": 0, "speed_upload": 0, "assigned_groups": "[]",
        "allowed_profiles": "[]", "lan_access": 0,
    }


def _wire_users(monkeypatch, rows, access=None):
    wire = _Wire()
    marks = {"synced": [], "error": [], "deleted": []}
    monkeypatch.setattr(proxima_client, "request", wire)
    monkeypatch.setattr(vpn_user_sync, "get_pending_access", lambda sid=None: rows)
    monkeypatch.setattr(vpn_user_sync, "get_all_vpn_servers", lambda: [SHV, SVR, KLM])
    monkeypatch.setattr(vpn_user_sync, "get_user_access", lambda uid: (access or {}).get(uid, []))
    monkeypatch.setattr(vpn_user_sync, "mark_access_synced",
                        lambda rid, **kw: marks["synced"].append(rid))
    monkeypatch.setattr(vpn_user_sync, "mark_access_error",
                        lambda rid, err: marks["error"].append((rid, err)))
    monkeypatch.setattr(vpn_user_sync, "delete_user_access",
                        lambda uid, sid: marks["deleted"].append((uid, sid)))
    return wire, marks


# ── the gate ─────────────────────────────────────────────────────────────────

def test_a_dead_site_is_asked_once(monkeypatch):
    wire = _Wire()
    monkeypatch.setattr(proxima_client, "request", wire)
    gate = SiteGate()
    assert gate.call(KLM, "GET", "/api/vpn/users") == (None, proxima_client.UNREACHABLE)
    assert gate.call(KLM, "PUT", "/api/vpn/users/1", body={}) == (None, proxima_client.UNREACHABLE)
    assert len(wire.to("KLM")) == 1


def test_pushes_split_the_timeout(monkeypatch):
    wire = _Wire()
    monkeypatch.setattr(proxima_client, "request", wire)
    SiteGate().call(SHV, "PUT", "/api/vpn/users/1", body={})
    connect, read = wire.calls[0][3]
    assert connect <= 5 < read
    # Longer than the slowest healthy connect we have measured (SHV, 1.1 s).
    assert connect >= 3


def test_an_application_error_does_not_close_the_gate(monkeypatch):
    monkeypatch.setattr(proxima_client, "request",
                        lambda *a, **kw: _Resp(status=400, error="max_peers out of range"))
    gate = SiteGate()
    assert gate.call(SHV, "PUT", "/x", body={}) == (None, "max_peers out of range")
    assert not gate.is_down(SHV)


def test_the_next_run_remembers_and_a_manual_one_does_not(monkeypatch):
    wire = _Wire()
    monkeypatch.setattr(proxima_client, "request", wire)
    SiteGate().call(KLM, "GET", "/x")

    assert SiteGate().is_down(KLM)
    assert not SiteGate(fresh=True).is_down(KLM)

    SiteGate().call(KLM, "GET", "/x")
    assert len(wire.to("KLM")) == 1
    SiteGate(fresh=True).call(KLM, "GET", "/x")
    assert len(wire.to("KLM")) == 2


def test_the_memory_runs_out(monkeypatch):
    wire = _Wire()
    monkeypatch.setattr(proxima_client, "request", wire)
    SiteGate().call(KLM, "GET", "/x")
    real = proxima_client.time.time
    monkeypatch.setattr(proxima_client.time, "time",
                        lambda: real() + proxima_client.DOWN_MEMORY + 1)
    assert not SiteGate().is_down(KLM)


def test_a_site_that_answers_again_is_forgiven(monkeypatch):
    wire = _Wire()
    monkeypatch.setattr(proxima_client, "request", wire)
    SiteGate().call(KLM, "GET", "/x")
    wire.dead.clear()
    SiteGate(fresh=True).call(KLM, "GET", "/x")
    assert not SiteGate().is_down(KLM)


# ── user sync ────────────────────────────────────────────────────────────────

def test_the_other_sites_are_served_while_one_is_down(monkeypatch):
    rows = [
        _row(1, "anna", KLM, remote=11),
        _row(2, "boris", KLM, remote=12),
        _row(3, "anna", SHV, remote=21),
        _row(4, "vera", KLM),
        _row(5, "boris", SVR, remote=31),
    ]
    wire, marks = _wire_users(monkeypatch, rows)

    result = vpn_user_sync.sync_pending()

    assert result["updated"] == ["anna@SHV", "boris@SVR"]
    assert marks["synced"] == [3, 5]
    assert result["failed"] == []
    assert [d["target"] for d in result["deferred"]] == ["anna@KLM", "boris@KLM", "vera@KLM"]
    assert result["unreachable_servers"] == ["KLM"]
    # Three rows, one attempt: the cost of a dead site is one connect timeout.
    assert len(wire.to("KLM")) == 1


def test_waiting_rows_stay_queued_and_say_why(monkeypatch):
    rows = [_row(1, "anna", KLM, remote=11), _row(2, "boris", KLM, status="pending_delete", remote=12)]
    _, marks = _wire_users(monkeypatch, rows)

    vpn_user_sync.sync_pending()

    # mark_access_error leaves sync_status alone — the row is retried.
    assert [rid for rid, _ in marks["error"]] == [1, 2]
    assert all("waiting" in err for _, err in marks["error"])
    assert marks["synced"] == [] and marks["deleted"] == []


def test_a_waiting_row_is_not_rewritten_every_run(monkeypatch):
    row = _row(1, "anna", KLM, remote=11)
    row["sync_error"] = proxima_client.waiting_note(proxima_client.UNREACHABLE)
    _, marks = _wire_users(monkeypatch, [row])

    result = vpn_user_sync.sync_pending()

    assert len(result["deferred"]) == 1
    assert marks["error"] == []


def test_a_revocation_that_never_left_adm_needs_no_site(monkeypatch):
    rows = [_row(1, "anna", KLM, remote=11), _row(2, "boris", KLM, status="pending_delete")]
    wire, marks = _wire_users(monkeypatch, rows)

    result = vpn_user_sync.sync_pending()

    assert result["removed"] == ["boris@KLM"]
    assert marks["deleted"] == [(2, KLM["id"])]
    assert len(wire.to("KLM")) == 1


def test_a_refusal_is_still_a_failure(monkeypatch):
    rows = [_row(1, "anna", SHV, remote=21)]
    _, marks = _wire_users(monkeypatch, rows)
    monkeypatch.setattr(proxima_client, "request",
                        lambda *a, **kw: _Resp(status=400, error="max_peers out of range"))

    result = vpn_user_sync.sync_pending()

    assert result["deferred"] == []
    assert result["failed"] == [{"target": "anna@SHV", "error": "max_peers out of range",
                                 "action": "updated"}]
    assert marks["error"] == [(1, "max_peers out of range")]


def test_a_new_grant_does_not_wait_on_a_dead_site_for_the_password(monkeypatch):
    # anna already exists on KLM (down) and SVR; she is being added to SHV.
    rows = [_row(1, "anna", SHV, user_id=7)]
    rows[0]["password_changed_at"] = 0
    access = {7: [
        {"vpn_server_id": KLM["id"], "server_name": "KLM", "remote_user_id": 11,
         "sync_status": "synced", "password_synced_at": 5},
        {"vpn_server_id": SVR["id"], "server_name": "SVR", "remote_user_id": 31,
         "sync_status": "synced", "password_synced_at": 5},
    ]}
    wire, marks = _wire_users(monkeypatch, rows, access)

    result = vpn_user_sync.sync_pending()

    assert result["created"] == ["anna@SHV"]
    assert marks["synced"] == [1]
    assert len(wire.to("KLM")) == 1
    assert [c[1] for c in wire.to("SVR")] == ["GET"]


def test_password_reconcile_asks_a_dead_site_once(monkeypatch):
    wire = _Wire()
    monkeypatch.setattr(proxima_client, "request", wire)
    monkeypatch.setattr(vpn_user_sync, "get_all_vpn_servers", lambda: [SHV, SVR, KLM])
    monkeypatch.setattr(vpn_user_sync, "get_all_vpn_users", lambda: [])

    result = vpn_user_sync.reconcile_passwords()

    assert result["unreachable_servers"] == ["KLM"]
    assert len(wire.to("KLM")) == 1


# ── panel admin sync ─────────────────────────────────────────────────────────

def test_panel_access_is_pushed_past_a_dead_site(monkeypatch):
    rows = [
        {"id": 1, "admin_id": 1, "vpn_server_id": 6, "server_name": "KLM", "username": "can",
         "sync_status": "pending", "password_hash": "h", "sync_error": None},
        {"id": 2, "admin_id": 2, "vpn_server_id": 6, "server_name": "KLM", "username": "ops",
         "sync_status": "pending_delete", "password_hash": "h", "sync_error": None},
        {"id": 3, "admin_id": 1, "vpn_server_id": 2, "server_name": "SHV", "username": "can",
         "sync_status": "pending", "password_hash": "h", "sync_error": None},
    ]
    wire = _Wire()
    synced, errors, deleted = [], [], []
    monkeypatch.setattr(proxima_client, "request", wire)
    monkeypatch.setattr(admin_sync, "get_pending_admin_access", lambda sid=None: rows)
    monkeypatch.setattr(admin_sync, "get_all_vpn_servers", lambda: [SHV, SVR, KLM])
    monkeypatch.setattr(admin_sync, "mark_admin_access_synced",
                        lambda rid, **kw: synced.append(rid))
    monkeypatch.setattr(admin_sync, "mark_admin_access_error",
                        lambda rid, err: errors.append(rid))
    monkeypatch.setattr(admin_sync, "delete_admin_access",
                        lambda aid, sid: deleted.append((aid, sid)))

    result = admin_sync.sync_pending()

    assert result["granted"] == ["can@SHV"]
    assert synced == [3]
    assert result["failed"] == []
    assert [d["target"] for d in result["deferred"]] == ["can@KLM", "ops@KLM"]
    # The revocation is kept until the site confirms it.
    assert deleted == []
    assert errors == [1, 2]
    assert len(wire.to("KLM")) == 1
