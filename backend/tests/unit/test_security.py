import pytest
import jwt

from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_access_token,
    decode_refresh_token,
    hash_password,
    hash_token,
    verify_password,
)
from app.core.config import settings
from app.core.exceptions.auth import InvalidTokenError

# hash_password / verify_password
def test_hash_password_returns_hashed_string():
    result = hash_password("SecurePass1!")
    assert result != "SecurePass1!"
    assert result.startswith("$2b$")

def test_verify_password_correct():
    hashed = hash_password("SecurePass1!")
    assert verify_password("SecurePass1!", hashed) is True

def test_verify_password_wrong():
    hashed = hash_password("SecurePass1!")
    assert verify_password("WrongPass1!", hashed) is False

def test_hash_password_max_length_raises():
    with pytest.raises(ValueError, match="72 bytes"):
        hash_password("a" * 73)

# hash_token
def test_hash_token_is_deterministic():
    assert hash_token("some-raw-token") == hash_token("some-raw-token")

def test_hash_token_different_inputs_differ():
    assert hash_token("token-a") != hash_token("token-b")

def test_hash_token_returns_hex_string():
    result = hash_token("any-value")
    assert len(result) == 64
    int(result, 16)

# create_access_token / decode_access_token
def test_create_access_token_returns_token_and_jti():
    token, jti = create_access_token(user_id="user-123", email="test@example.com")
    assert isinstance(token, str)
    assert isinstance(jti, str)
    assert len(jti) > 0

def test_decode_access_token_round_trips():
    token, jti = create_access_token(user_id="user-123", email="test@example.com")
    decoded = decode_access_token(token)
    assert decoded["user_id"] == "user-123"
    assert decoded["email"] == "test@example.com"
    assert decoded["jti"] == jti

def test_decode_access_token_invalid_raises():
    with pytest.raises(InvalidTokenError):
        decode_access_token("not.a.valid.token")

def test_decode_access_token_wrong_secret_raises():
    payload = {"sub": "user-123", "jti": "some-jti", "email": "x@x.com"}
    bad_token = jwt.encode(payload, "wrong-secret", algorithm=settings.jwt_algorithm)
    with pytest.raises(InvalidTokenError):
        decode_access_token(bad_token)

def test_decode_access_token_missing_sub_raises():
    payload = {"jti": "some-jti"}
    token = jwt.encode(payload, settings.jwt_access_secret, algorithm=settings.jwt_algorithm)
    with pytest.raises(InvalidTokenError):
        decode_access_token(token)

def test_decode_access_token_missing_jti_raises():
    payload = {"sub": "user-123"}
    token = jwt.encode(payload, settings.jwt_access_secret, algorithm=settings.jwt_algorithm)
    with pytest.raises(InvalidTokenError):
        decode_access_token(token)

# create_refresh_token / decode_refresh_token
def test_create_refresh_token_returns_token_and_hash():
    token, token_hash = create_refresh_token(user_id="user-123")
    assert isinstance(token, str)
    assert isinstance(token_hash, str)
    assert len(token_hash) == 64

def test_decode_refresh_token_round_trips():
    token, token_hash = create_refresh_token(user_id="user-123")
    decoded = decode_refresh_token(token)
    assert decoded["user_id"] == "user-123"
    assert decoded["token_hash"] == token_hash

def test_decode_refresh_token_invalid_raises():
    with pytest.raises(InvalidTokenError):
        decode_refresh_token("garbage.token.here")

def test_decode_refresh_token_wrong_secret_raises():
    payload = {"sub": "user-123", "jti": "raw-token-value"}
    bad_token = jwt.encode(payload, "wrong-secret", algorithm=settings.jwt_algorithm)
    with pytest.raises(InvalidTokenError):
        decode_refresh_token(bad_token)

def test_two_refresh_tokens_have_different_hashes():
    _, hash_a = create_refresh_token(user_id="user-123")
    _, hash_b = create_refresh_token(user_id="user-123")
    assert hash_a != hash_b
