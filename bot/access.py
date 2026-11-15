"""Вход в квест только по ссылке t.me/бот?start=<секрет>."""

from __future__ import annotations

import hmac
import os
import re

_CODE = re.compile(r"^[A-Za-z0-9_-]{8,64}$")


def access_code() -> str:
    value = os.environ.get("ACCESS_CODE", "").strip()
    if _CODE.fullmatch(value) is None:
        raise SystemExit(
            "В .env нет ACCESS_CODE из 8–64 символов (латиница, цифры, _ и -). "
            "Ссылка для туристов: https://t.me/<бот>?start=<этот_секрет>"
        )
    return value


def link_grants(given: str | None, expected: str | None = None) -> bool:
    code = access_code() if expected is None else expected
    candidate = (given or "").strip()
    if len(candidate) != len(code):
        return False
    return hmac.compare_digest(candidate, code)
