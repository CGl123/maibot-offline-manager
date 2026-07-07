"""下线管理持久化存储"""

from datetime import datetime
from pathlib import Path
from typing import Any, Dict

import json


def _offline_state_path() -> Path:
    from src.config.config import global_config

    return Path(global_config.plugin.data_dir) / "offline_manager_state.json"


def save_offline_state(
    offline_until: datetime | None,
    offline_started_at: datetime | None,
    offline_reason: str = "",
) -> None:
    payload: Dict[str, Any] = {
        "offline_until": offline_until.isoformat() if offline_until else None,
        "offline_started_at": offline_started_at.isoformat() if offline_started_at else None,
        "offline_reason": offline_reason,
    }
    path = _offline_state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def load_offline_state() -> tuple[datetime | None, datetime | None, str]:
    path = _offline_state_path()
    if not path.exists():
        return None, None, ""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None, None, ""

    raw_until = payload.get("offline_until")
    if not raw_until:
        return None, None, ""
    try:
        offline_until = datetime.fromisoformat(str(raw_until))
    except (ValueError, TypeError):
        return None, None, ""

    if offline_until <= datetime.now():
        return None, None, ""

    raw_started = payload.get("offline_started_at")
    offline_started_at: datetime | None = None
    if raw_started:
        try:
            offline_started_at = datetime.fromisoformat(str(raw_started))
        except (ValueError, TypeError):
            pass

    return offline_until, offline_started_at, str(payload.get("offline_reason") or "")


def clear_offline_state() -> None:
    path = _offline_state_path()
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass
