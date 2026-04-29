"""Tests for db_backup.safe_copy_db.

The bot continually writes to market_tape.db while backups run; shutil.copy2
under those conditions produced corrupt daily snapshots starting 2026-04-23.
These tests verify the replacement uses the SQLite online-backup API
correctly: integrity preserved under concurrent writes, atomic destination,
non-SQLite fallback.
"""
import os
import sqlite3
import tempfile
import threading
import time

from db_backup import safe_copy_db


def _open_with_writes(path: str) -> sqlite3.Connection:
    c = sqlite3.connect(path, timeout=30)
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("CREATE TABLE IF NOT EXISTS t (id INTEGER PRIMARY KEY, v INTEGER)")
    c.commit()
    return c


def test_copy_produces_valid_sqlite():
    with tempfile.TemporaryDirectory() as d:
        src = os.path.join(d, "src.db")
        dst = os.path.join(d, "dst.db")
        c = _open_with_writes(src)
        c.executemany("INSERT INTO t (v) VALUES (?)", [(i,) for i in range(100)])
        c.commit()
        c.close()

        safe_copy_db(src, dst)

        d_conn = sqlite3.connect(dst)
        rows = d_conn.execute("SELECT COUNT(*) FROM t").fetchone()[0]
        ok = d_conn.execute("PRAGMA quick_check").fetchone()[0]
        d_conn.close()
        assert rows == 100
        assert ok == "ok"


def test_copy_under_concurrent_writes():
    with tempfile.TemporaryDirectory() as d:
        src = os.path.join(d, "src.db")
        dst = os.path.join(d, "dst.db")

        seed = _open_with_writes(src)
        seed.executemany("INSERT INTO t (v) VALUES (?)", [(i,) for i in range(50)])
        seed.commit()
        seed.close()

        stop = threading.Event()
        writer_err: list[BaseException] = []

        def writer():
            try:
                conn = sqlite3.connect(src, timeout=30)
                n = 1000
                while not stop.is_set():
                    conn.execute("INSERT INTO t (v) VALUES (?)", (n,))
                    conn.commit()
                    n += 1
                    time.sleep(0.001)
                conn.close()
            except BaseException as e:
                writer_err.append(e)

        t = threading.Thread(target=writer, daemon=True)
        t.start()
        try:
            time.sleep(0.05)
            safe_copy_db(src, dst)
        finally:
            stop.set()
            t.join(timeout=2)

        assert not writer_err, f"writer thread errored: {writer_err[0]!r}"

        d_conn = sqlite3.connect(dst)
        ok = d_conn.execute("PRAGMA quick_check").fetchone()[0]
        rows = d_conn.execute("SELECT COUNT(*) FROM t").fetchone()[0]
        d_conn.close()
        assert ok == "ok"
        assert rows >= 50  # at least the seeded rows


def test_atomic_dst_no_tmp_left_behind():
    with tempfile.TemporaryDirectory() as d:
        src = os.path.join(d, "src.db")
        dst = os.path.join(d, "dst.db")
        c = _open_with_writes(src)
        c.execute("INSERT INTO t (v) VALUES (1)")
        c.commit()
        c.close()

        safe_copy_db(src, dst)
        assert os.path.exists(dst)
        assert not os.path.exists(dst + ".tmp")


def test_overwrites_stale_tmp():
    with tempfile.TemporaryDirectory() as d:
        src = os.path.join(d, "src.db")
        dst = os.path.join(d, "dst.db")
        c = _open_with_writes(src)
        c.execute("INSERT INTO t (v) VALUES (1)")
        c.commit()
        c.close()

        # Simulate a leftover tmp from a previous crashed run.
        with open(dst + ".tmp", "wb") as f:
            f.write(b"garbage")

        safe_copy_db(src, dst)
        assert os.path.exists(dst)
        assert not os.path.exists(dst + ".tmp")


def test_non_sqlite_falls_back_to_copy():
    with tempfile.TemporaryDirectory() as d:
        src = os.path.join(d, "plain.txt")
        dst = os.path.join(d, "plain_copy.txt")
        with open(src, "wb") as f:
            f.write(b"not a sqlite database")

        safe_copy_db(src, dst)
        with open(dst, "rb") as f:
            assert f.read() == b"not a sqlite database"
