"""Import boundaries. Strategy and agents cannot reach a broker submit path."""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "packages" / "quantos"

BANNED = {
    "strategy": {"quantos.brokers", "quantos.execution", "alpaca"},
    "agents": {"quantos.brokers", "quantos.execution", "alpaca"},
    "features": {"quantos.research.labels", "quantos.brokers"},
}


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                found.add(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.add(node.module)
    return found


def test_layer_imports_stay_inside_their_boundary():
    for package, banned in BANNED.items():
        for path in (ROOT / package).rglob("*.py"):
            imports = _imports(path)
            illegal = [name for name in imports if any(name == item or name.startswith(item + ".") for item in banned)]
            assert not illegal, f"{path} imports {illegal}"


def test_no_eval_in_the_trading_packages():
    for path in ROOT.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                assert node.func.id not in {"eval", "exec"}
