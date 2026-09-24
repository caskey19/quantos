"""Local scanners. They do not phone home."""

from __future__ import annotations

import re
import sys
from pathlib import Path

PATTERNS = [
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"-----BEGIN (?:RSA |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"(?i)(api_secret|secret_key)\s*[:=]\s*['\"][^'\"]{8,}['\"]"),
]
SKIP = {".git", "node_modules", ".venv", "venv", "data", "dist", "__pycache__"}


def scan(root: Path) -> list[str]:
    hits: list[str] = []
    for path in root.rglob("*"):
        if any(part in SKIP for part in path.parts):
            continue
        if not path.is_file() or path.suffix.lower() in {".parquet", ".png", ".pyc"}:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for pattern in PATTERNS:
            if pattern.search(text):
                hits.append(str(path))
                break
    return hits


def main() -> None:
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.cwd()
    hits = scan(root)
    if hits:
        print("secret scan failed")
        for hit in hits:
            print(hit)
        raise SystemExit(1)
    print("secret scan passed")


if __name__ == "__main__":
    main()
