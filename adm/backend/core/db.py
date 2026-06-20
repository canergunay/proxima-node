"""SQLite database — shared connection, schema init, CRUD helpers."""

import sqlite3
import threading
import time

from core.config import DB_PATH

_conn_lock = threading.Lock()
_shared_conn: sqlite3.Connection | None = None


def get_conn() -> sqlite3.Connection:
    """Return the shared database connection (thread-safe)."""
    global _shared_conn
    if _shared_conn is None:
        with _conn_lock:
            if _shared_conn is None:
                _shared_conn = sqlite3.connect(DB_PATH, check_same_thread=False)
                _shared_conn.row_factory = sqlite3.Row
                _shared_conn.execute("PRAGMA foreign_keys = ON")
                _shared_conn.execute("PRAGMA journal_mode = WAL")
                _shared_conn.execute("PRAGMA synchronous = NORMAL")
                _shared_conn.execute("PRAGMA busy_timeout = 5000")
    return _shared_conn


def init_db() -> None:
    """Create tables if they don't exist."""
    conn = get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS servers (
            id                    INTEGER PRIMARY KEY AUTOINCREMENT,
            name                  TEXT NOT NULL UNIQUE,
            display_name          TEXT NOT NULL,
            ip                    TEXT NOT NULL,
            server_type           TEXT NOT NULL,
            location              TEXT NOT NULL DEFAULT '',
            provider              TEXT NOT NULL DEFAULT '',
            status                TEXT NOT NULL DEFAULT 'new',
            root_password_enc     TEXT,
            ss_password_enc       TEXT,
            agent_api_key_enc     TEXT,
            ssconf_token_enc      TEXT,
            speedtest_api_key_enc TEXT,
            ss_port               INTEGER NOT NULL DEFAULT 8388,
            ss_cipher             TEXT NOT NULL DEFAULT 'chacha20-ietf-poly1305',
            agent_port            INTEGER NOT NULL DEFAULT 5051,
            node_id               TEXT,
            install_adguard       INTEGER NOT NULL DEFAULT 0,
            created_at            INTEGER NOT NULL,
            updated_at            INTEGER NOT NULL
        );

        CREATE TABLE IF NOT EXISTS operations (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            server_id    INTEGER,
            op_type      TEXT NOT NULL,
            status       TEXT NOT NULL DEFAULT 'running',
            playbook     TEXT,
            output       TEXT NOT NULL DEFAULT '',
            error        TEXT,
            started_at   INTEGER NOT NULL,
            completed_at INTEGER,
            FOREIGN KEY (server_id) REFERENCES servers(id) ON DELETE SET NULL
        );

        CREATE TABLE IF NOT EXISTS admins (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            username      TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            created_at    INTEGER NOT NULL
        );

        CREATE TABLE IF NOT EXISTS vpn_servers (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            name            TEXT NOT NULL UNIQUE,
            display_name    TEXT NOT NULL,
            url             TEXT NOT NULL,
            api_token_enc   TEXT,
            created_at      INTEGER NOT NULL,
            updated_at      INTEGER NOT NULL
        );
    """)
    conn.commit()

    # Schema migrations
    _migrate(conn)


def _migrate(conn: sqlite3.Connection) -> None:
    """Run schema migrations for columns added after initial release."""
    cols = {row[1] for row in conn.execute("PRAGMA table_info(servers)").fetchall()}
    if "ssh_port" not in cols:
        conn.execute("ALTER TABLE servers ADD COLUMN ssh_port INTEGER NOT NULL DEFAULT 22")
        conn.commit()
    if "vless_uuid" not in cols:
        conn.execute("ALTER TABLE servers ADD COLUMN vless_uuid TEXT")
        conn.execute("ALTER TABLE servers ADD COLUMN vless_public_key TEXT")
        conn.execute("ALTER TABLE servers ADD COLUMN vless_short_id TEXT")
        conn.execute("ALTER TABLE servers ADD COLUMN vless_port INTEGER DEFAULT 8443")
        conn.commit()

    # vpn_servers migrations
    vpn_cols = {row[1] for row in conn.execute("PRAGMA table_info(vpn_servers)").fetchall()}
    if "public_url" not in vpn_cols:
        conn.execute("ALTER TABLE vpn_servers ADD COLUMN public_url TEXT DEFAULT ''")
        conn.commit()


# ── Server CRUD ──────────────────────────────────────────────────────────

def create_server(data: dict) -> int:
    conn = get_conn()
    ts = int(time.time())
    cur = conn.execute(
        "INSERT INTO servers (name, display_name, ip, server_type, location, provider, "
        "status, root_password_enc, ss_password_enc, agent_api_key_enc, ssconf_token_enc, "
        "speedtest_api_key_enc, ss_port, ss_cipher, agent_port, node_id, install_adguard, "
        "created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            data["name"], data["display_name"], data["ip"], data["server_type"],
            data.get("location", ""), data.get("provider", ""),
            data.get("status", "new"),
            data.get("root_password_enc"), data.get("ss_password_enc"),
            data.get("agent_api_key_enc"), data.get("ssconf_token_enc"),
            data.get("speedtest_api_key_enc"),
            data.get("ss_port", 8388), data.get("ss_cipher", "chacha20-ietf-poly1305"),
            data.get("agent_port", 5051), data.get("node_id"),
            1 if data.get("install_adguard") else 0,
            ts, ts,
        ),
    )
    conn.commit()
    return cur.lastrowid


def get_server(server_id: int) -> dict | None:
    conn = get_conn()
    row = conn.execute("SELECT * FROM servers WHERE id = ?", (server_id,)).fetchone()
    return dict(row) if row else None


def get_server_by_name(name: str) -> dict | None:
    conn = get_conn()
    row = conn.execute("SELECT * FROM servers WHERE name = ?", (name,)).fetchone()
    return dict(row) if row else None


def get_all_servers() -> list[dict]:
    conn = get_conn()
    rows = conn.execute("SELECT * FROM servers ORDER BY id").fetchall()
    return [dict(r) for r in rows]


def update_server(server_id: int, updates: dict) -> bool:
    conn = get_conn()
    allowed = {
        "name", "display_name", "ip", "server_type", "location", "provider",
        "status", "root_password_enc", "ss_password_enc", "agent_api_key_enc",
        "ssconf_token_enc", "speedtest_api_key_enc", "ss_port", "ss_cipher",
        "agent_port", "ssh_port", "node_id", "install_adguard",
        "vless_uuid", "vless_public_key", "vless_short_id", "vless_port",
    }
    sets, vals = [], []
    for key, val in updates.items():
        if key in allowed:
            sets.append(f"{key} = ?")
            vals.append(val)
    if not sets:
        return False
    sets.append("updated_at = ?")
    vals.append(int(time.time()))
    vals.append(server_id)
    conn.execute(f"UPDATE servers SET {', '.join(sets)} WHERE id = ?", vals)
    conn.commit()
    return True


def delete_server(server_id: int) -> bool:
    conn = get_conn()
    cur = conn.execute("DELETE FROM servers WHERE id = ?", (server_id,))
    conn.commit()
    return cur.rowcount > 0


def server_count() -> int:
    conn = get_conn()
    row = conn.execute("SELECT COUNT(*) as cnt FROM servers").fetchone()
    return row["cnt"] if row else 0


# ── Operations CRUD ──────────────────────────────────────────────────────

def create_operation(server_id: int | None, op_type: str, playbook: str | None = None) -> int:
    conn = get_conn()
    ts = int(time.time())
    cur = conn.execute(
        "INSERT INTO operations (server_id, op_type, status, playbook, output, started_at) "
        "VALUES (?, ?, 'running', ?, '', ?)",
        (server_id, op_type, playbook, ts),
    )
    conn.commit()
    return cur.lastrowid


def get_operation(op_id: int) -> dict | None:
    conn = get_conn()
    row = conn.execute("SELECT * FROM operations WHERE id = ?", (op_id,)).fetchone()
    return dict(row) if row else None


def get_operations(limit: int = 50) -> list[dict]:
    conn = get_conn()
    rows = conn.execute(
        "SELECT id, server_id, op_type, status, playbook, error, started_at, completed_at "
        "FROM operations ORDER BY id DESC LIMIT ?",
        (limit,),
    ).fetchall()
    return [dict(r) for r in rows]


def get_operations_by_server(server_id: int, limit: int = 20) -> list[dict]:
    conn = get_conn()
    rows = conn.execute(
        "SELECT id, server_id, op_type, status, playbook, error, started_at, completed_at "
        "FROM operations WHERE server_id = ? ORDER BY id DESC LIMIT ?",
        (server_id, limit),
    ).fetchall()
    return [dict(r) for r in rows]


def append_operation_output(op_id: int, text: str) -> None:
    conn = get_conn()
    conn.execute(
        "UPDATE operations SET output = output || ? WHERE id = ?",
        (text, op_id),
    )
    conn.commit()


def complete_operation(op_id: int, status: str, error: str | None = None) -> None:
    conn = get_conn()
    conn.execute(
        "UPDATE operations SET status = ?, error = ?, completed_at = ? WHERE id = ?",
        (status, error, int(time.time()), op_id),
    )
    conn.commit()


# ── Admin CRUD ───────────────────────────────────────────────────────────

def create_admin(username: str, password_hash: str) -> int:
    conn = get_conn()
    ts = int(time.time())
    cur = conn.execute(
        "INSERT INTO admins (username, password_hash, created_at) VALUES (?, ?, ?)",
        (username, password_hash, ts),
    )
    conn.commit()
    return cur.lastrowid


def get_admin_by_username(username: str) -> dict | None:
    conn = get_conn()
    row = conn.execute(
        "SELECT id, username, password_hash, created_at FROM admins WHERE username = ?",
        (username,),
    ).fetchone()
    return dict(row) if row else None


def admin_count() -> int:
    conn = get_conn()
    row = conn.execute("SELECT COUNT(*) as cnt FROM admins").fetchone()
    return row["cnt"] if row else 0


def update_admin_password(admin_id: int, password_hash: str) -> bool:
    conn = get_conn()
    cur = conn.execute(
        "UPDATE admins SET password_hash = ? WHERE id = ?",
        (password_hash, admin_id),
    )
    conn.commit()
    return cur.rowcount > 0


# ── VPN Server CRUD ─────────────────────────────────────────────────────

def create_vpn_server(data: dict) -> int:
    conn = get_conn()
    ts = int(time.time())
    cur = conn.execute(
        "INSERT INTO vpn_servers (name, display_name, url, public_url, api_token_enc, "
        "created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            data["name"], data["display_name"], data["url"],
            data.get("public_url", ""), data.get("api_token_enc"),
            ts, ts,
        ),
    )
    conn.commit()
    return cur.lastrowid


def get_vpn_server(vpn_server_id: int) -> dict | None:
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM vpn_servers WHERE id = ?", (vpn_server_id,)
    ).fetchone()
    return dict(row) if row else None


def get_all_vpn_servers() -> list[dict]:
    conn = get_conn()
    rows = conn.execute("SELECT * FROM vpn_servers ORDER BY id").fetchall()
    return [dict(r) for r in rows]


def update_vpn_server(vpn_server_id: int, updates: dict) -> bool:
    conn = get_conn()
    allowed = {"name", "display_name", "url", "public_url", "api_token_enc"}
    sets, vals = [], []
    for key, val in updates.items():
        if key in allowed:
            sets.append(f"{key} = ?")
            vals.append(val)
    if not sets:
        return False
    sets.append("updated_at = ?")
    vals.append(int(time.time()))
    vals.append(vpn_server_id)
    conn.execute(f"UPDATE vpn_servers SET {', '.join(sets)} WHERE id = ?", vals)
    conn.commit()
    return True


def delete_vpn_server(vpn_server_id: int) -> bool:
    conn = get_conn()
    cur = conn.execute("DELETE FROM vpn_servers WHERE id = ?", (vpn_server_id,))
    conn.commit()
    return cur.rowcount > 0
