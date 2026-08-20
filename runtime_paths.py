"""Runtime paths — local Windows vs Vercel serverless (/tmp)."""

from __future__ import annotations

import os

HERE = os.path.dirname(os.path.abspath(__file__))
IS_VERCEL = os.environ.get("VERCEL") == "1"


def data_root() -> str:
    if IS_VERCEL:
        root = os.environ.get("FSS_DATA_DIR", "/tmp/fss-invoice")
        os.makedirs(root, exist_ok=True)
        return root
    return HERE


def invoices_dir() -> str:
    path = os.path.join(data_root(), "Invoices")
    os.makedirs(path, exist_ok=True)
    return path
