"""Small helpers shared across the package."""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import datetime
from pathlib import Path


class Utils:
    @staticmethod
    def to_dict(obj):
        """Convert results (dataclasses, lists of them) into JSON-friendly data."""
        if isinstance(obj, list):
            return [Utils.to_dict(o) for o in obj]
        if is_dataclass(obj):
            return {k: Utils.to_dict(v) for k, v in asdict(obj).items()}
        if isinstance(obj, dict):
            return {k: Utils.to_dict(v) for k, v in obj.items()}
        if isinstance(obj, datetime):
            return obj.isoformat()
        if isinstance(obj, Path):
            return str(obj)
        return obj

    @staticmethod
    def unique_path(path: Path) -> Path:
        """path, or "name (1).ext", "name (2).ext"... if it already exists."""
        n = 1
        candidate = path
        while candidate.exists():
            candidate = path.with_name(f"{path.stem} ({n}){path.suffix}")
            n += 1
        return candidate
