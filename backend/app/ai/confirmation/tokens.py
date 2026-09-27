"""HMAC-signed confirmation tokens for AI write tools."""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.core.config import settings

DEFAULT_TTL_SECONDS = 600  # 10 minutes


class PendingActionPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_id: int
    tool_name: str
    arguments: dict[str, Any]
    summary: str
    exp: int
    target_type: str | None = None
    target_id: int | None = None


class PendingConfirmationView(BaseModel):
    """API-facing pending confirmation (token is opaque)."""

    model_config = ConfigDict(extra="forbid")

    token: str
    tool_name: str
    summary: str
    expires_at: int


class ConfirmationError(Exception):
    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


def _secret() -> bytes:
    raw = (getattr(settings, "ai_confirmation_secret", None) or settings.secret_key or "").strip()
    if not raw:
        raw = "dev-ai-confirmation-secret"
    return raw.encode("utf-8")


def arguments_digest(arguments: dict[str, Any]) -> str:
    canonical = json.dumps(arguments, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def create_confirmation_token(
    *,
    user_id: int,
    tool_name: str,
    arguments: dict[str, Any],
    summary: str,
    target_type: str | None = None,
    target_id: int | None = None,
    ttl_seconds: int = DEFAULT_TTL_SECONDS,
) -> tuple[str, PendingActionPayload]:
    payload = PendingActionPayload(
        user_id=user_id,
        tool_name=tool_name,
        arguments=arguments,
        summary=summary,
        exp=int(time.time()) + max(60, ttl_seconds),
        target_type=target_type,
        target_id=target_id,
    )
    body = payload.model_dump_json()
    sig = hmac.new(_secret(), body.encode("utf-8"), hashlib.sha256).hexdigest()
    # token = base64url-ish compact: hex(body_bytes).hex(sig) is awkward; use length-prefixed
    import base64

    raw = body.encode("utf-8") + b"." + sig.encode("utf-8")
    token = base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")
    return token, payload


def verify_confirmation_token(token: str, *, user_id: int) -> PendingActionPayload:
    import base64

    padded = token + "=" * (-len(token) % 4)
    try:
        raw = base64.urlsafe_b64decode(padded.encode("ascii"))
    except Exception as exc:
        raise ConfirmationError("Invalid confirmation token") from exc

    if b"." not in raw:
        raise ConfirmationError("Invalid confirmation token")
    body, sig = raw.rsplit(b".", 1)
    expected = hmac.new(_secret(), body, hashlib.sha256).hexdigest().encode("utf-8")
    if not hmac.compare_digest(sig, expected):
        raise ConfirmationError("Invalid confirmation token")

    try:
        payload = PendingActionPayload.model_validate_json(body)
    except Exception as exc:
        raise ConfirmationError("Invalid confirmation token") from exc

    if payload.user_id != user_id:
        raise ConfirmationError("Confirmation token does not belong to this user")
    if int(time.time()) > payload.exp:
        raise ConfirmationError("Confirmation token has expired")
    return payload
