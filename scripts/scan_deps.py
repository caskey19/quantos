"""Dependency name scan. pip-audit is invoked when it is installed."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

BANNED = ("pycrypto", "django<1.0", "pyyaml<5.1")


def main() -> None:
    text = Path("pyproject.toml").read_text(encoding="utf-8").lower()
    for name in BANNED:
        if name in text:
            print(f"banned dependency pin: {name}")
            raise SystemExit(1)
    import importlib.util

    if importlib.util.find_spec("pip_audit") is None:
        print("pip-audit is not installed; banned-name scan passed")
        return
    completed = subprocess.run([sys.executable, "-m", "pip_audit"], check=False)
    raise SystemExit(completed.returncode)


if __name__ == "__main__":
    main()
