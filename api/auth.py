"""Telegram Mini App (WebApp) initData HMAC-SHA256 authentication."""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from urllib.parse import parse_qsl

import config


class AuthError(Exception):
    """Raised when Telegram Mini App authentication fails."""


@dataclass(frozen=True)
class TelegramUser:
    id: int
    username: str | None = None
    first_name: str | None = None
    last_name: str | None = None

    @property
    def display_username(self) -> str | None:
        if self.username:
            return self.username
        parts = [p for p in (self.first_name, self.last_name) if p]
        return " ".join(parts) if parts else None


def verify_init_data(
    init_data: str,
    bot_token: str | None = None,
    max_age_seconds: int | None = 86400,
) -> TelegramUser:
    """Verify Telegram WebApp initData signature using HMAC-SHA256.

    Follows the official Telegram Mini Apps validation algorithm:
      secret_key = HMAC-SHA256("WebAppData", bot_token)
      data_check_string = "\\n".join(f"{k}={v}" for k, v in sorted(params))
      hash == HMAC-SHA256(secret_key, data_check_string).hexdigest()
    """
    raw = (init_data or "").strip()
    if not raw:
        raise AuthError("Empty Telegram initData")

    token = bot_token if bot_token is not None else config.BOT_TOKEN
    if not token:
        raise AuthError("BOT_TOKEN is not configured")

    pairs = parse_qsl(raw, keep_blank_values=True, strict_parsing=False)
    if not pairs:
        raise AuthError("Malformed Telegram initData")

    params: dict[str, str] = {}
    for key, value in pairs:
        params[key] = value

    received_hash = params.pop("hash", "").strip().lower()
    if not received_hash:
        raise AuthError("Missing hash in Telegram initData")

    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(params.items()))
    secret_key = hmac.new(b"WebAppData", token.encode("utf-8"), hashlib.sha256).digest()
    expected_hash = hmac.new(
        secret_key,
        data_check_string.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(expected_hash, received_hash):
        raise AuthError("Invalid Telegram initData signature")

    if max_age_seconds is not None and "auth_date" in params:
        try:
            auth_date = int(params["auth_date"])
        except ValueError as exc:
            raise AuthError("Invalid auth_date in Telegram initData") from exc
        if time.time() - auth_date > max_age_seconds:
            raise AuthError("Telegram initData has expired")

    user_raw = params.get("user")
    if not user_raw:
        raise AuthError("Missing user payload in Telegram initData")

    try:
        user_data = json.loads(user_raw)
    except json.JSONDecodeError as exc:
        raise AuthError("Invalid user JSON in Telegram initData") from exc

    if not isinstance(user_data, dict) or not isinstance(user_data.get("id"), int):
        raise AuthError("Invalid user object in Telegram initData")

    return TelegramUser(
        id=user_data["id"],
        username=user_data.get("username") or None,
        first_name=user_data.get("first_name") or None,
        last_name=user_data.get("last_name") or None,
    )


def authenticate_init_data(
    init_data: str | None,
    bot_token: str | None = None,
    dev_user_id: int | None = None,
) -> TelegramUser:
    """Authenticate a Mini App request.

    Allows local dev bypass ONLY when `init_data` is empty and
    `WEBAPP_DEV_USER_ID` (or `dev_user_id`) is explicitly configured.
    """
    raw = (init_data or "").strip()
    if raw:
        return verify_init_data(raw, bot_token=bot_token)

    effective_dev_uid = dev_user_id if dev_user_id is not None else config.WEBAPP_DEV_USER_ID
    if effective_dev_uid is not None:
        return TelegramUser(
            id=int(effective_dev_uid),
            username="dev_operator",
            first_name="Dev",
            last_name="Operator",
        )

    raise AuthError("Missing X-Telegram-Init-Data header")
