"""Unit tests: Training resource_url validation (Phase 10.1B)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.modules.training.schemas import TrainingCreateRequest, TrainingUpdateRequest


def test_create_accepts_https_url():
    payload = TrainingCreateRequest(
        title="Safety",
        resource_url="https://learn.example.com/course/1",
    )
    assert payload.resource_url == "https://learn.example.com/course/1"


def test_create_accepts_http_url():
    payload = TrainingCreateRequest(
        title="Safety",
        resource_url="http://intranet.local/training",
    )
    assert payload.resource_url == "http://intranet.local/training"


def test_create_omitted_url_is_none():
    payload = TrainingCreateRequest(title="Safety")
    assert payload.resource_url is None


def test_create_blank_url_becomes_none():
    payload = TrainingCreateRequest(title="Safety", resource_url="  ")
    assert payload.resource_url is None


def test_create_rejects_javascript_scheme():
    with pytest.raises(ValidationError):
        TrainingCreateRequest(title="Safety", resource_url="javascript:alert(1)")


def test_create_rejects_malformed_url():
    with pytest.raises(ValidationError):
        TrainingCreateRequest(title="Safety", resource_url="not-a-url")


def test_update_accepts_null_to_clear():
    payload = TrainingUpdateRequest(resource_url=None)
    assert payload.resource_url is None
    assert "resource_url" in payload.model_dump(exclude_unset=True)


def test_update_rejects_ftp_scheme():
    with pytest.raises(ValidationError):
        TrainingUpdateRequest(resource_url="ftp://files.example.com/course")
