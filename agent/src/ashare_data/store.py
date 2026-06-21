"""Initializer and lightweight inspector for the local A-share DuckDB store."""

from __future__ import annotations

import os
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

import duckdb

from src.ashare_data.schema import (
    PR03_CORE_ALTERATIONS,
    PR03_CORE_TABLE_NAMES,
    PR03_CORE_TABLES,
    PR03_SCHEMA_VERSION,
)
from src.config.paths import get_data_dir

ASHARE_DATA_ROOT_ENV = "ASHARE_DATA_ROOT"
ASHARE_DATA_DB_PATH_ENV = "ASHARE_DATA_DB_PATH"
ASHARE_PARQUET_DIR_ENV = "ASHARE_PARQUET_DIR"


@dataclass(frozen=True)
class InitResult:
    """Result returned after ensuring the PR-03 local data store exists."""

    database_path: Path
    parquet_dir: Path
    schema_version: int
    tables: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-serializable result for scripts and acceptance checks."""
        return {
            "database_path": str(self.database_path),
            "parquet_dir": str(self.parquet_dir),
            "schema_version": self.schema_version,
            "tables": list(self.tables),
            "table_count": len(self.tables),
        }


def _expand_path(value: str | os.PathLike[str]) -> Path:
    return Path(value).expanduser().resolve()


def default_ashare_root() -> Path:
    """Return the default runtime root for A-share research data."""
    env_root = os.environ.get(ASHARE_DATA_ROOT_ENV)
    if env_root:
        return _expand_path(env_root)
    return get_data_dir() / "ashare"


def default_database_path() -> Path:
    """Return the default DuckDB database path for PR-03 data."""
    env_path = os.environ.get(ASHARE_DATA_DB_PATH_ENV)
    if env_path:
        return _expand_path(env_path)
    return default_ashare_root() / "ashare.duckdb"


def default_parquet_dir(database_path: Path | None = None) -> Path:
    """Return the default Parquet sidecar directory for the local store."""
    env_path = os.environ.get(ASHARE_PARQUET_DIR_ENV)
    if env_path:
        return _expand_path(env_path)
    if database_path is not None:
        return database_path.parent / "parquet"
    return default_ashare_root() / "parquet"


class AShareDataStore:
    """Local DuckDB store used by the A-share event strategy workbench."""

    def __init__(self, database_path: Path | str | None = None, parquet_dir: Path | str | None = None) -> None:
        self.database_path = _expand_path(database_path) if database_path is not None else default_database_path()
        self.parquet_dir = _expand_path(parquet_dir) if parquet_dir is not None else default_parquet_dir(self.database_path)

    @contextmanager
    def connect(self, *, read_only: bool = False) -> Iterator[duckdb.DuckDBPyConnection]:
        """Open a DuckDB connection and close it after use."""
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        # DuckDB rejects mixing read_only=True and read_only=False connections to
        # the same file inside one process. The local API serves concurrent
        # read and initialization requests, so keep one connection mode.
        with duckdb.connect(str(self.database_path), read_only=False) as conn:
            yield conn

    def initialize(self) -> InitResult:
        """Create the database file, Parquet directory, and PR-03 core tables.

        The operation is idempotent: running it repeatedly preserves existing
        rows and only creates missing tables/directories.
        """
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self.parquet_dir.mkdir(parents=True, exist_ok=True)

        with self.connect(read_only=False) as conn:
            for table in PR03_CORE_TABLES:
                conn.execute(table.sql)
            for statement in PR03_CORE_ALTERATIONS:
                conn.execute(statement)

        return InitResult(
            database_path=self.database_path,
            parquet_dir=self.parquet_dir,
            schema_version=PR03_SCHEMA_VERSION,
            tables=self.list_tables(),
        )

    def list_tables(self) -> tuple[str, ...]:
        """Return PR-03 table names currently present in the DuckDB database."""
        with self.connect(read_only=True) as conn:
            rows = conn.execute(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'main'
                ORDER BY table_name
                """
            ).fetchall()
        present = {str(row[0]) for row in rows}
        return tuple(name for name in PR03_CORE_TABLE_NAMES if name in present)

    def table_columns(self, table_name: str) -> tuple[str, ...]:
        """Return column names for one initialized table."""
        with self.connect(read_only=True) as conn:
            rows = conn.execute(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = 'main' AND table_name = ?
                ORDER BY ordinal_position
                """,
                [table_name],
            ).fetchall()
        return tuple(str(row[0]) for row in rows)


def initialize_ashare_store(database_path: Path | str | None = None, parquet_dir: Path | str | None = None) -> InitResult:
    """Initialize the local A-share data store and return the resulting paths."""
    return AShareDataStore(database_path=database_path, parquet_dir=parquet_dir).initialize()
