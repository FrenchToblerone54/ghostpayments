import sqlite3
import os
from flask import g, current_app

SCHEMA_VERSION = 1

def get_db():
    if "db" not in g:
        db_path = current_app.config["DB_PATH"]
        os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
        g.db = sqlite3.connect(db_path, check_same_thread=False)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA journal_mode=WAL")
        g.db.execute("PRAGMA foreign_keys=ON")
        g.db.execute("PRAGMA busy_timeout=5000")
    return g.db

def open_db(db_path=None):
    db_path = db_path or os.getenv("DB_PATH", "data/ghost.db")
    os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
    db = sqlite3.connect(db_path, check_same_thread=False)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA foreign_keys=ON")
    db.execute("PRAGMA busy_timeout=5000")
    return db

def init_db(db_path=None):
    db_path = db_path or os.getenv("DB_PATH", "data/ghost.db")
    os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
    db = sqlite3.connect(db_path, check_same_thread=False)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA foreign_keys=ON")
    db.execute("PRAGMA busy_timeout=5000")
    version = db.execute("PRAGMA user_version").fetchone()[0]
    if version == 0:
        _apply_initial_schema(db)
    _run_migrations(db, version)
    db.close()

def _apply_initial_schema(db):
    db.executescript("""
        CREATE TABLE IF NOT EXISTS invoices (
            id              TEXT PRIMARY KEY,
            chain           TEXT NOT NULL CHECK(chain IN ('BSC','POLYGON')),
            token           TEXT NOT NULL CHECK(token IN ('USDT','BNB','POL')),
            amount_native   TEXT NOT NULL,
            amount_usd      REAL,
            deposit_address TEXT NOT NULL,
            hd_index        INTEGER NOT NULL,
            status          TEXT NOT NULL DEFAULT 'pending'
                            CHECK(status IN ('pending','underpaid','confirming',
                                             'sweeping','completed','expired','failed')),
            tx_in_hash      TEXT,
            gas_tx_hash     TEXT,
            tx_out_hash     TEXT,
            webhook_url     TEXT,
            metadata        TEXT,
            created_at      TEXT NOT NULL,
            expires_at      TEXT NOT NULL,
            confirmed_at    TEXT,
            completed_at    TEXT
        );

        CREATE TABLE IF NOT EXISTS api_keys (
            id              TEXT PRIMARY KEY,
            label           TEXT NOT NULL,
            key_hash        TEXT NOT NULL UNIQUE,
            key_prefix      TEXT NOT NULL,
            is_active       INTEGER NOT NULL DEFAULT 1,
            created_at      TEXT NOT NULL,
            last_used_at    TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_invoices_status    ON invoices(status);
        CREATE INDEX IF NOT EXISTS idx_invoices_chain     ON invoices(chain);
        CREATE INDEX IF NOT EXISTS idx_invoices_created   ON invoices(created_at);
        CREATE INDEX IF NOT EXISTS idx_api_keys_hash      ON api_keys(key_hash);

        PRAGMA user_version = 1;
    """)
    db.commit()

def _run_migrations(db, current_version):
    pass
