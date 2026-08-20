"""Audit trail — logs user actions to SQL Server."""

from __future__ import annotations

import db


def log(user: str, action: str, entity_type: str = "", entity_id: str = "",
        details: str = "", ip: str = "") -> None:
    try:
        with db.get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                "EXEC dbo.sp_LogAudit ?,?,?,?,?,?",
                user or "system", action, entity_type or None,
                entity_id or None, details or None, ip or None)
            conn.commit()
    except Exception:  # noqa: BLE001
        pass
