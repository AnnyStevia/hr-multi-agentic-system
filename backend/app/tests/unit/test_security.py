import pytest

from app.core.security import create_access_token, get_password_hash, verify_password


def test_password_hashing():
    password = "securepassword123"
    hashed = get_password_hash(password)
    assert hashed != password
    assert verify_password(password, hashed)
    assert not verify_password("wrongpassword", hashed)


def test_create_and_decode_token():
    from app.core.security import decode_access_token

    token = create_access_token({"sub": "1", "email": "test@example.com"})
    payload = decode_access_token(token)
    assert payload is not None
    assert payload["sub"] == "1"
    assert payload["email"] == "test@example.com"
