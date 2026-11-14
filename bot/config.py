"""Пути и токен. Токен читается из окружения или из файла .env."""

from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MEDIA_DIR = ROOT / "media"


def load_env() -> None:
    path = ROOT / ".env"
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


load_env()

DATA_DIR = Path(os.environ.get("DATA_DIR", ROOT / "data"))


def token() -> str:
    value = os.environ.get("BOT_TOKEN", "").strip()
    if not value:
        raise SystemExit("В .env нет BOT_TOKEN. Токен создаётся в @BotFather.")
    return value
