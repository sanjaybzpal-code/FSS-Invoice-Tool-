"""Runtime paths — local Windows vs Vercel serverless (/tmp)."""

from __future__ import annotations

import os

HERE = os.path.dirname(os.path.abspath(__file__))
# VERCEL_ENV is set only on Vercel — ignore stray VERCEL=1 on local Windows.
IS_VERCEL = bool(os.environ.get("VERCEL_ENV"))


def is_vercel() -> bool:
    return IS_VERCEL


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
