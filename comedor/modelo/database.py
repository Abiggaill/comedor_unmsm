"""Singleton database factory for local SQLite and Render PostgreSQL."""

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from threading import RLock


class SingletonMeta(type):
    """Return one shared database configuration per process."""

    _instances = {}
    _lock = RLock()

    def __call__(cls, *args, **kwargs):
        with cls._lock:
            if cls not in cls._instances:
                cls._instances[cls] = super().__call__(*args, **kwargs)
            return cls._instances[cls]


class _Connection:
    """Small SQL adapter so the MVC models can use either database driver."""

    def __init__(self, raw, postgres=False):
        self.raw = raw
        self.postgres = postgres

    def execute(self, sql, parameters=()):
        if self.postgres:
            sql = sql.replace("?", "%s")
        return self.raw.execute(sql, parameters)


class Database(metaclass=SingletonMeta):
    """Singleton connection factory; every operation gets its own connection."""

    def __init__(self, database_path=None):
        self.database_url = os.environ.get("DATABASE_URL", "").strip()
        self.is_postgres = bool(self.database_url)
        if self.is_postgres:
            if self.database_url.startswith("postgres://"):
                self.database_url = self.database_url.replace("postgres://", "postgresql://", 1)
            self.path = None
        else:
            project_root = Path(__file__).resolve().parents[2]
            configured_path = database_path or os.environ.get("DATABASE_PATH")
            self.path = Path(configured_path).expanduser() if configured_path else project_root / "comedor.db"
            self.path.parent.mkdir(parents=True, exist_ok=True)

    @property
    def integrity_error(self):
        if self.is_postgres:
            import psycopg

            return psycopg.IntegrityError
        return sqlite3.IntegrityError

    @property
    def database_error(self):
        if self.is_postgres:
            import psycopg

            return psycopg.Error
        return sqlite3.Error

    @contextmanager
    def connection(self, immediate=False):
        if self.is_postgres:
            from psycopg.rows import dict_row

            raw = None
            try:
                import psycopg

                raw = psycopg.connect(self.database_url, row_factory=dict_row)
                conn = _Connection(raw, postgres=True)
                if immediate:
                    # Serializes creation/reservation operations across workers.
                    conn.execute("SELECT pg_advisory_xact_lock(736281904)")
                yield conn
                raw.commit()
            except Exception:
                if raw is not None:
                    raw.rollback()
                raise
            finally:
                if raw is not None:
                    raw.close()
            return

        raw = sqlite3.connect(str(self.path), timeout=10)
        raw.row_factory = sqlite3.Row
        raw.execute("PRAGMA foreign_keys = ON")
        conn = _Connection(raw)
        try:
            if immediate:
                conn.execute("BEGIN IMMEDIATE")
            yield conn
            raw.commit()
        except Exception:
            raw.rollback()
            raise
        finally:
            raw.close()


db = Database()
