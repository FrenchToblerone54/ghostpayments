import os
import sqlite3
import pytest
import tempfile
from app.db import init_db, open_db

@pytest.fixture
def tmp_db(tmp_path):
    db_path = str(tmp_path / "test.db")
    os.environ["DB_PATH"] = db_path
    init_db(db_path)
    yield db_path
    os.unlink(db_path)

def test_schema_version(tmp_db):
    db = open_db(tmp_db)
    version = db.execute("PRAGMA user_version").fetchone()[0]
    assert version == 1
    db.close()

def test_invoices_table_exists(tmp_db):
    db = open_db(tmp_db)
    tables = db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    names = [t[0] for t in tables]
    assert "invoices" in names
    assert "api_keys" in names
    db.close()

def test_invoices_columns(tmp_db):
    db = open_db(tmp_db)
    cols = db.execute("PRAGMA table_info(invoices)").fetchall()
    col_names = [c[1] for c in cols]
    for expected in ("id", "chain", "token", "amount_native", "deposit_address", "hd_index", "status", "webhook_url", "metadata", "created_at", "expires_at"):
        assert expected in col_names
    db.close()

def test_api_keys_columns(tmp_db):
    db = open_db(tmp_db)
    cols = db.execute("PRAGMA table_info(api_keys)").fetchall()
    col_names = [c[1] for c in cols]
    for expected in ("id", "label", "key_hash", "key_prefix", "is_active", "created_at", "last_used_at"):
        assert expected in col_names
    db.close()

def test_wal_mode(tmp_db):
    db = open_db(tmp_db)
    mode = db.execute("PRAGMA journal_mode").fetchone()[0]
    assert mode == "wal"
    db.close()

def test_idempotent_init(tmp_db):
    init_db(tmp_db)
    db = open_db(tmp_db)
    version = db.execute("PRAGMA user_version").fetchone()[0]
    assert version == 1
    db.close()
