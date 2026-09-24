"""Process settings and the live-trading lock.

Live submission is unreachable unless every independent gate passes.
No function in this module creates the unlock file.
"""

from __future__ import annotations

import os
from pathlib import Path

import yaml
from pydantic import BaseModel, Field

UNLOCK_PHRASE = "I_AUTHORIZE_LIVE_TRADING_FOR_QUANT_OS"
LOOPBACK = {"127.0.0.1", "localhost", "::1"}


class CredentialIsolationError(RuntimeError):
    pass


class LiveTradingDisabled(RuntimeError):
    pass


class PublicBindError(RuntimeError):
    pass


class Settings(BaseModel):
    trading_mode: str = "paper"
    bind_host: str = "127.0.0.1"
    bind_port: int = 8000
    database_url: str = "sqlite:///data/ops/quantos.sqlite"
    data_root: Path = Path("data")
    paper_key: str = ""
    paper_secret: str = ""
    paper_base_url: str = "https://paper-api.alpaca.markets"
    live_key: str = ""
    live_secret: str = ""
    live_base_url: str = "https://api.alpaca.markets"
    unlock_path: Path = Path("secrets/live.unlock")
    checklist_path: Path = Path("config/live_authorization.yml")
    sealed_path: Path = Path("config/sealed_window.yml")
    risk_path: Path = Path("config/risk_limits.yml")
    repo_root: Path = Field(default_factory=lambda: Path.cwd())
    in_docker: bool = False

    def validate_boot(self) -> None:
        if self.paper_key and self.live_key:
            raise CredentialIsolationError(
                "Paper and live credentials are both set. Refusing to start."
            )
        if self.bind_host not in LOOPBACK and not self.in_docker:
            raise PublicBindError(f"Refusing non-loopback bind host {self.bind_host}")
        if self.trading_mode == "live":
            assert_live_allowed(self)
        elif self.trading_mode not in {"paper", "shadow"}:
            raise LiveTradingDisabled(f"Unknown trading mode {self.trading_mode}")


def load_settings(env: dict[str, str] | None = None, root: Path | None = None) -> Settings:
    source = os.environ if env is None else env
    repo = root or Path.cwd()
    settings = Settings(
        trading_mode=source.get("TRADING_MODE", "paper").strip().lower(),
        bind_host=source.get("QUANTOS_BIND_HOST", "127.0.0.1"),
        bind_port=int(source.get("QUANTOS_BIND_PORT", "8000")),
        database_url=source.get("DATABASE_URL", "sqlite:///data/ops/quantos.sqlite"),
        data_root=Path(source.get("DATA_ROOT", "data")),
        paper_key=source.get("APCA_API_KEY_ID", "").strip(),
        paper_secret=source.get("APCA_API_SECRET_KEY", "").strip(),
        paper_base_url=source.get("APCA_API_BASE_URL", "https://paper-api.alpaca.markets"),
        live_key=source.get("APCA_LIVE_API_KEY_ID", "").strip(),
        live_secret=source.get("APCA_LIVE_API_SECRET_KEY", "").strip(),
        live_base_url=source.get("APCA_LIVE_API_BASE_URL", "https://api.alpaca.markets"),
        unlock_path=Path(source.get("QUANTOS_UNLOCK_PATH", "secrets/live.unlock")),
        checklist_path=Path(source.get("QUANTOS_CHECKLIST_PATH", str(repo / "config" / "live_authorization.yml"))),
        sealed_path=Path(source.get("QUANTOS_SEALED_PATH", str(repo / "config" / "sealed_window.yml"))),
        risk_path=Path(source.get("QUANTOS_RISK_PATH", str(repo / "config" / "risk_limits.yml"))),
        repo_root=repo,
        in_docker=source.get("QUANTOS_IN_DOCKER") == "1",
    )
    settings.validate_boot()
    return settings


def checklist_items(path: Path) -> dict[str, bool]:
    if not path.exists():
        return {}
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    items = payload.get("items") or {}
    return {str(key): bool(value) for key, value in items.items()}


def checklist_complete(path: Path) -> bool:
    items = checklist_items(path)
    return bool(items) and all(items.values())


def unlock_matches(path: Path) -> bool:
    if not path.exists() or not path.is_file():
        return False
    return path.read_text(encoding="utf-8").strip() == UNLOCK_PHRASE


def assert_live_allowed(settings: Settings) -> None:
    """Raise unless every live gate is already true. Does not create any gate."""
    missing: list[str] = []
    if settings.trading_mode != "live":
        missing.append("TRADING_MODE is not live")
    if not unlock_matches(settings.unlock_path):
        missing.append("unlock file absent or phrase mismatch")
    if not checklist_complete(settings.checklist_path):
        missing.append("live checklist incomplete")
    if not settings.live_key or not settings.live_secret:
        missing.append("live credentials absent")
    if settings.paper_key or settings.paper_secret:
        missing.append("paper credentials are loaded in this process")
    if "paper-api" in settings.live_base_url:
        missing.append("live base URL points at the paper host")
    if missing:
        raise LiveTradingDisabled("Live trading is disabled: " + "; ".join(missing))


def live_status(settings: Settings) -> dict[str, object]:
    try:
        assert_live_allowed(settings)
        allowed = True
        reason = ""
    except LiveTradingDisabled as exc:
        allowed = False
        reason = str(exc)
    return {
        "mode": settings.trading_mode,
        "live_submission_allowed": allowed,
        "reason": reason,
        "checklist": checklist_items(settings.checklist_path),
        "unlock_present": unlock_matches(settings.unlock_path),
    }
