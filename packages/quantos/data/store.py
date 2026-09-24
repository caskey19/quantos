"""Immutable raw market data and derived parquet datasets."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import duckdb
import pandas as pd


class RawDataOverwrite(RuntimeError):
    pass


class ParquetStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.raw = root / "raw"
        self.processed = root / "processed"
        self.manifest = root / "manifest.jsonl"
        self.raw.mkdir(parents=True, exist_ok=True)
        self.processed.mkdir(parents=True, exist_ok=True)

    def write_raw(self, frame: pd.DataFrame, dataset: str, source: str) -> Path:
        blob = frame.to_parquet(index=False)
        digest = hashlib.sha256(blob).hexdigest()
        path = self.raw / dataset / source / f"{digest}.parquet"
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            return path
        path.write_bytes(blob)
        record = {
            "dataset": dataset,
            "source": source,
            "sha256": digest,
            "rows": int(len(frame)),
            "path": str(path),
            "written_at": datetime.now(timezone.utc).isoformat(),
            "kind": "raw",
        }
        with self.manifest.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record) + "\n")
        return path

    def write_processed(self, frame: pd.DataFrame, dataset: str, version: str) -> Path:
        """Derived data gets a new versioned file. It never replaces a raw file."""
        blob = frame.to_parquet(index=False)
        digest = hashlib.sha256(blob).hexdigest()[:16]
        path = self.processed / dataset / f"{version}-{digest}.parquet"
        if path.exists():
            raise RawDataOverwrite(f"Refusing to overwrite {path}")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(blob)
        return path

    def scan(self, dataset: str, source: str) -> pd.DataFrame:
        pattern = (self.raw / dataset / source / "*.parquet").as_posix()
        if not list((self.raw / dataset / source).glob("*.parquet")):
            return pd.DataFrame()
        return duckdb.sql(f"SELECT * FROM read_parquet('{pattern}')").df()
