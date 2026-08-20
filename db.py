"""SQL Server connection and schema migration for FSS Accounts."""

from __future__ import annotations

import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(HERE, "config.json")
SQL_DIR = os.path.join(HERE, "database")


def _is_vercel() -> bool:
    return os.environ.get("VERCEL") == "1"


def _import_pyodbc():
    import pyodbc
    return pyodbc


def load_config() -> dict:
    if os.environ.get("CONFIG_JSON"):
        try:
            return json.loads(os.environ["CONFIG_JSON"])
        except json.JSONDecodeError:
            pass
    with open(CONFIG_PATH, "r", encoding="utf-8") as fh:
        return json.load(fh)


def connection_string(config: dict | None = None) -> str:
    env_cs = os.environ.get("AZURE_SQL_CONNECTION_STRING") or os.environ.get("SQL_CONNECTION_STRING")
    if env_cs:
        return env_cs.strip()
    db = (config or load_config()).get("database", {})
    driver = db.get("driver", "ODBC Driver 17 for SQL Server")
    server = db.get("server", "(local)")
    database = db.get("database", "FSSInvoice")
    if db.get("trusted_connection", True):
        return f"DRIVER={{{driver}}};SERVER={server};DATABASE={database};Trusted_Connection=yes;"
    return (
        f"DRIVER={{{driver}}};SERVER={server};DATABASE={database};"
        f"UID={db.get('username', '')};PWD={db.get('password', '')};"
    )


def master_connection_string(config: dict | None = None) -> str:
    db = (config or load_config()).get("database", {})
    driver = db.get("driver", "ODBC Driver 17 for SQL Server")
    server = db.get("server", "(local)")
    if db.get("trusted_connection", True):
        return f"DRIVER={{{driver}}};SERVER={server};DATABASE=master;Trusted_Connection=yes;"
    return (
        f"DRIVER={{{driver}}};SERVER={server};DATABASE=master;"
        f"UID={db.get('username', '')};PWD={db.get('password', '')};"
    )


def get_connection(config: dict | None = None):
    """SQL Server — pymssql on Vercel; pyodbc on Windows."""
    if _is_vercel():
        if not os.environ.get("AZURE_SQL_HOST"):
            raise RuntimeError(
                "Set AZURE_SQL_HOST, AZURE_SQL_USER, AZURE_SQL_PASSWORD on Vercel.")
        import pymssql
        db_cfg = (config or load_config()).get("database", {})
        return pymssql.connect(
            server=os.environ["AZURE_SQL_HOST"],
            user=os.environ.get("AZURE_SQL_USER") or db_cfg.get("username", ""),
            password=os.environ.get("AZURE_SQL_PASSWORD") or db_cfg.get("password", ""),
            database=os.environ.get("AZURE_SQL_DATABASE") or db_cfg.get("database", "FSSInvoice"),
        )
    pyodbc = _import_pyodbc()
    return pyodbc.connect(connection_string(config), autocommit=False)


def _split_batches(sql: str) -> list[str]:
    parts = re.split(r"\bGO\b", sql, flags=re.IGNORECASE)
    return [p.strip() for p in parts if p.strip()]


def _run_sql_file(cursor, path: str) -> None:
    with open(path, "r", encoding="utf-8") as fh:
        sql = fh.read()
    for batch in _split_batches(sql):
        cursor.execute(batch)


def migrate(config: dict | None = None) -> str:
    """Create database and apply all scripts. Safe to run multiple times."""
    cfg = config or load_config()
    if _is_vercel() and not os.environ.get("AZURE_SQL_HOST"):
        return "Skipped migration on Vercel (no AZURE_SQL_* env)."

    if not _is_vercel():
        pyodbc = _import_pyodbc()
        with pyodbc.connect(master_connection_string(cfg), autocommit=True) as conn:
            cur = conn.cursor()
            _run_sql_file(cur, os.path.join(SQL_DIR, "01_create_database.sql"))

    scripts = ("02_tables.sql", "03_views.sql", "04_stored_procedures.sql",
               "05_ar_extensions.sql", "06_ar_views.sql", "07_ar_stored_procedures.sql",
               "09_segments_expenses.sql", "10_segment_views.sql",
               "11_non_gst_bills.sql", "12_receipts_proforma.sql")
    with get_connection(cfg) as conn:
        cur = conn.cursor()
        for name in scripts:
            _run_sql_file(cur, os.path.join(SQL_DIR, name))
            conn.commit()
    return "Database migrated successfully."


def test_connection(config: dict | None = None) -> tuple[bool, str]:
    try:
        with get_connection(config) as conn:
            cur = conn.cursor()
            cur.execute("SELECT DB_NAME()")
            row = cur.fetchone()
            return True, f"Connected to {row[0]}"
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)
