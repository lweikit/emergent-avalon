import hashlib
import hmac
import secrets
from typing import Dict

from fastapi import HTTPException


# Maps "session_id:player_id" → sha256(token)
_player_tokens: Dict[str, str] = {}


def issue_token(session_id: str, player_id: str) -> str:
    """Issue a random token for a player in a session."""
    token = secrets.token_urlsafe(32)
    _player_tokens[f"{session_id}:{player_id}"] = hashlib.sha256(token.encode()).hexdigest()
    return token


def verify_token(session_id: str, player_id: str, token: str) -> bool:
    """Verify a player's token."""
    key = f"{session_id}:{player_id}"
    expected = _player_tokens.get(key)
    if not expected:
        return False
    return hmac.compare_digest(expected, hashlib.sha256(token.encode()).hexdigest())


def require_auth(session_id: str, player_id: str, player_token: str):
    """Raise 403 if the token doesn't match the player."""
    if not player_token or not verify_token(session_id, player_id, player_token):
        raise HTTPException(status_code=403, detail="Invalid player token")


def cleanup_session_tokens(session_id: str):
    """Remove all tokens for a given session."""
    prefix = f"{session_id}:"
    keys = [k for k in _player_tokens if k.startswith(prefix)]
    for k in keys:
        del _player_tokens[k]
