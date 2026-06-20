"""Command line helpers for the local A-share data store."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.ashare_data.store import initialize_ashare_store


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Initialize the local A-share DuckDB data store.")
    parser.add_argument("--db-path", type=Path, default=None, help="DuckDB path. Defaults to ~/.vibe-trading/ashare/ashare.duckdb.")
    parser.add_argument("--parquet-dir", type=Path, default=None, help="Parquet sidecar directory. Defaults next to the DuckDB file.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable initialization metadata.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    result = initialize_ashare_store(database_path=args.db_path, parquet_dir=args.parquet_dir)

    if args.json:
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    else:
        print("A 股本地数据仓库已就绪")
        print(f"数据库: {result.database_path}")
        print(f"Parquet 目录: {result.parquet_dir}")
        print(f"核心表: {len(result.tables)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
