"""Couche d'accès à la base SQL centrale.

Toutes les interfaces (Dash, API REST, front web, Angular, et le dashboard
R Shiny) attaquent le même fichier SQLite décrit par ``shared/schema.sql``.
C'est ce qui rend les données des départements réellement centralisées :
il n'existe qu'un seul jeu de tables, un seul jeu de triggers et un seul
jeu de vues consolidées.
"""

from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Sequence

from .config import MIGRATIONS_PATH, PROJECT_ROOT, SCHEMA_PATH

DB_PATH = Path(os.environ.get("ERP_DB_PATH", PROJECT_ROOT / "data" / "erp.db"))


def _configure(conn: sqlite3.Connection) -> sqlite3.Connection:
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 5000")
    return conn


def connect(db_path: str | Path | None = None) -> sqlite3.Connection:
    """Ouvre une connexion configurée sur la base centrale."""
    path = Path(db_path) if db_path else DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    return _configure(sqlite3.connect(str(path), check_same_thread=False))


def _columns(conn: sqlite3.Connection, table: str) -> set[str]:
    """Noms des colonnes d'une table, vide si la table n'existe pas."""
    return {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}


def apply_migrations(conn: sqlite3.Connection) -> list[str]:
    """Met à niveau une base déjà remplie, d'après ``shared/migrations.json``.

    ``schema.sql`` ne contient que des ``CREATE ... IF NOT EXISTS`` : il crée
    une base neuve mais laisse intacte une base existante. Sans cette étape,
    une base créée par une version antérieure garderait ses anciennes colonnes
    et les écritures échoueraient (« table company has no column named ... »).

    Chaque opération n'agit que si l'ancien état est réellement présent, ce
    qui rend la fonction rejouable sans risque.
    """
    if not MIGRATIONS_PATH.exists():
        return []

    plan = json.loads(MIGRATIONS_PATH.read_text(encoding="utf-8"))
    appliquees: list[str] = []

    for regle in plan.get("colonnes_renommees", []):
        table, ancien, nouveau = regle["table"], regle["de"], regle["vers"]
        colonnes = _columns(conn, table)
        if ancien in colonnes and nouveau not in colonnes:
            conn.execute(f'ALTER TABLE "{table}" RENAME COLUMN "{ancien}" TO "{nouveau}"')
            appliquees.append(f"{table}.{ancien} -> {nouveau}")

    for regle in plan.get("colonnes_ajoutees", []):
        table, colonne = regle["table"], regle["colonne"]
        if colonne not in _columns(conn, table) and _columns(conn, table):
            conn.execute(f'ALTER TABLE "{table}" ADD COLUMN "{colonne}" {regle["type"]}')
            appliquees.append(f"{table}.{colonne} ajoutée")

    if appliquees:
        conn.commit()
    return appliquees


def init_schema(conn: sqlite3.Connection) -> None:
    """Applique ``shared/schema.sql`` puis les migrations des bases existantes."""
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    conn.commit()
    apply_migrations(conn)


class Database:
    """Façade fine sur SQLite : requêtes, écritures et journal d'audit."""

    def __init__(self, db_path: str | Path | None = None) -> None:
        self.path = Path(db_path) if db_path else DB_PATH
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = connect(self.path)
        init_schema(self._conn)

    # -- cycle de vie ----------------------------------------------------
    @property
    def conn(self) -> sqlite3.Connection:
        return self._conn

    def close(self) -> None:
        self._conn.close()

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        try:
            yield self._conn
            self._conn.commit()
        except Exception:
            self._conn.rollback()
            raise

    # -- lecture ---------------------------------------------------------
    def query(self, sql: str, params: Sequence[Any] | dict[str, Any] = ()) -> list[dict]:
        cur = self._conn.execute(sql, params)
        rows = [dict(r) for r in cur.fetchall()]
        cur.close()
        return rows

    def one(self, sql: str, params: Sequence[Any] | dict[str, Any] = ()) -> dict | None:
        rows = self.query(sql, params)
        return rows[0] if rows else None

    def scalar(self, sql: str, params: Sequence[Any] | dict[str, Any] = (), default: Any = 0) -> Any:
        row = self.one(sql, params)
        if not row:
            return default
        value = next(iter(row.values()))
        return default if value is None else value

    def dataframe(self, sql: str, params: Sequence[Any] | dict[str, Any] = ()):
        """Retourne un DataFrame pandas (import paresseux : l'API n'en a pas besoin)."""
        import pandas as pd

        return pd.read_sql_query(sql, self._conn, params=params)

    # -- écriture --------------------------------------------------------
    def execute(self, sql: str, params: Sequence[Any] | dict[str, Any] = ()) -> int:
        cur = self._conn.execute(sql, params)
        self._conn.commit()
        last = cur.lastrowid
        cur.close()
        return last

    def executemany(self, sql: str, seq: Sequence[Sequence[Any]]) -> None:
        self._conn.executemany(sql, seq)
        self._conn.commit()

    def log(self, department: str, entity: str, action: str,
            entity_id: int | None = None, detail: str = "") -> None:
        """Journalise une action dans le registre inter-départements."""
        self.execute(
            "INSERT INTO audit_log (department, entity, entity_id, action, detail)"
            " VALUES (?, ?, ?, ?, ?)",
            (department, entity, entity_id, action, detail),
        )

    # -- état de l'installation -----------------------------------------
    def is_configured(self) -> bool:
        """Vrai dès que l'onboarding a créé l'entreprise."""
        try:
            return self.scalar("SELECT COUNT(*) FROM company", default=0) > 0
        except sqlite3.Error:
            return False

    def company(self) -> dict | None:
        return self.one("SELECT * FROM company WHERE id = 1")

    def meta(self, key: str, default: Any = None) -> Any:
        row = self.one("SELECT value FROM app_meta WHERE key = ?", (key,))
        return row["value"] if row else default

    def set_meta(self, key: str, value: Any) -> None:
        self.execute(
            "INSERT INTO app_meta (key, value, updated_at) VALUES (?, ?, datetime('now'))"
            " ON CONFLICT(key) DO UPDATE SET value = excluded.value,"
            " updated_at = excluded.updated_at",
            (key, str(value)),
        )


_SINGLETON: Database | None = None


def get_db() -> Database:
    """Instance partagée par le processus courant (Dash, API...)."""
    global _SINGLETON
    if _SINGLETON is None:
        _SINGLETON = Database()
    return _SINGLETON
