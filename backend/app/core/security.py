"""
JWT validation bridge — decodes Auth.js v5 tokens issued by the Next.js frontend.

Auth.js v5 uses JWE (JSON Web Encryption) by default for its JWT tokens.
The shared AUTH_SECRET is used as the encryption key.
"""

import hashlib
import json
from dataclasses import dataclass

from jose import jwe, jwt
from jose.exceptions import JWEError, JWTError

from app.config import settings


@dataclass(frozen=True)
class CurrentUser:
    """Authenticated user extracted from Auth.js JWT."""

    user_id: str
    email: str
    name: str


def _derive_encryption_key(secret: str) -> bytes:
    """
    Auth.js v5 derives a 32-byte key from AUTH_SECRET using SHA-256
    for JWE encryption (dir + A256GCM).
    """
    return hashlib.sha256(secret.encode()).digest()


def decode_authjs_token(token: str) -> CurrentUser:
    """
    Decode an Auth.js v5 JWT token.

    Auth.js v5 issues JWE-encrypted tokens by default (alg=dir, enc=A256GCM).
    Falls back to plain JWS if the token is not encrypted.

    Raises ValueError on invalid or expired tokens.
    """
    key = _derive_encryption_key(settings.AUTH_SECRET)

    # Try JWE decryption first (Auth.js v5 default)
    try:
        payload_bytes = jwe.decrypt(token.encode(), key)
        payload = json.loads(payload_bytes)
    except (JWEError, json.JSONDecodeError, UnicodeDecodeError):
        # Fall back to JWS verification (if Auth.js configured for signed-only)
        try:
            payload = jwt.decode(
                token,
                settings.AUTH_SECRET,
                algorithms=["HS256"],
            )
        except JWTError as exc:
            raise ValueError(f"Invalid or expired token: {exc}") from exc

    # Auth.js v5 token shape:
    # { "sub": "user-id", "email": "...", "name": "...", "iat": ..., "exp": ... }
    user_id = payload.get("sub")
    email = payload.get("email", "")
    name = payload.get("name", "")

    if not user_id:
        raise ValueError("Token missing 'sub' claim")

    return CurrentUser(user_id=user_id, email=email, name=name)
