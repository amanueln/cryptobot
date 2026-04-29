"""Safe SQLite backup helper.

Uses the SQLite online-backup API to copy databases that may be open and
actively written to by another process. shutil.copy2 on a WAL-mode SQLite
under concurrent writes is what produced the corrupt daily backups starting
2026-04-23 — this module replaces that pattern.
"""
from __future__ import annotations

import os
import shutil
import sqlite3


def safe_copy_db(src: str, dst: str, timeout_s: int = 120) -> None:
    """Copy a SQLite DB safely using the online backup API.

    Writes to <dst>.tmp, then atomically renames to <dst> on success. Falls
    back to shutil.copy2 when src is not a SQLite file.
    """
    tmp = dst + ".tmp"
    if os.path.exists(tmp):
        os.remove(tmp)

    if not _is_sqlite(src):
        shutil.copy2(src, dst)
        return

    src_conn = sqlite3.connect(f"file:{src}?mode=ro", uri=True, timeout=timeout_s)
    try:
        dst_conn = sqlite3.connect(tmp, timeout=timeout_s)
        try:
            src_conn.backup(dst_conn)
        finally:
            dst_conn.close()
    finally:
        src_conn.close()
    os.replace(tmp, dst)


def _is_sqlite(path: str) -> bool:
    try:
        with open(path, "rb") as f:
            return f.read(16) == b"SQLite format 3\x00"
    except OSError:
        return False
