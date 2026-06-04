"""
JWT validation bridge — decodes Auth.js v5 tokens issued by the Next.js frontend.

Auth.js v5 uses JWE (JSON Web Encryption) by default for its JWT tokens.
The shared AUTH_SECRET is used as the encryption key.

JWE format: header.encrypted_key.iv.ciphertext.tag (compact serialization)
  - alg: "dir" (direct key usage — no key wrapping)
  - enc: "A256CBC-HS512" (AES-256-CBC + HMAC-SHA-512) — Auth.js v5 default
  - enc: "A256GCM" (AES-256-GCM) — alternate variant
"""

import base64
import hashlib
import hmac
import json
import struct
import time
from dataclasses import dataclass

import jwt as pyjwt
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives import hashes, padding
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from app.config import settings

# The cookie name used by Next.js for the session token
# This is used as the salt in HKDF key derivation
AUTHJS_COOKIE_NAME = "authjs.session-token"


@dataclass(frozen=True)
class CurrentUser:
    """Authenticated user extracted from Auth.js JWT."""

    user_id: str
    email: str
    name: str


def _derive_encryption_key(secret: str) -> bytes:
    """
    Auth.js v5 derives a 64-byte key from AUTH_SECRET using HKDF.

    For A256CBC-HS512 (64-byte CEK):
      - mac_key = key[:32]  (HMAC-SHA-512 authentication)
      - enc_key = key[32:]  (AES-256-CBC encryption)

    For A256GCM (32-byte CEK):
      - Uses key[32:] (last 32 bytes of the 64-byte derivation)

    Uses HKDF with:
    - Salt: The cookie name (authjs.session-token)
    - Info: "Auth.js Generated Encryption Key (authjs.session-token)"
    - Length: 64 bytes (to support A256CBC-HS512)
    - Algorithm: SHA-256
    """
    salt_bytes = AUTHJS_COOKIE_NAME.encode("utf-8")
    info_string = f"Auth.js Generated Encryption Key ({AUTHJS_COOKIE_NAME})".encode("utf-8")

    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=64,  # 64 bytes for A256CBC-HS512 (mac_key + enc_key)
        salt=salt_bytes,
        info=info_string,
    )
    return hkdf.derive(secret.encode("utf-8"))


def _base64url_decode(s: str) -> bytes:
    """Decode base64url without padding."""
    s += "=" * (4 - len(s) % 4)
    return base64.urlsafe_b64decode(s)


def _base64url_encode(data: bytes) -> str:
    """Encode bytes to base64url without padding."""
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _decrypt_a256cbc_hs512(
    key: bytes, iv: bytes, ciphertext: bytes, tag: bytes, aad: str
) -> bytes:
    """
    Decrypt A256CBC-HS512 (AES-256-CBC + HMAC-SHA-512) JWE content.

    The 64-byte CEK is split:
      - mac_key = key[:32]  (for HMAC-SHA-512)
      - enc_key = key[32:]  (for AES-256-CBC)

    Tag verification:
      AL = bit_length(AAD) as 64-bit big-endian
      M = HMAC-SHA-512(mac_key, AAD || IV || ciphertext || AL)
      tag must equal M[:32]
    """
    mac_key = key[:32]
    enc_key = key[32:]

    # Verify HMAC tag
    aad_bytes = aad.encode("ascii")
    al = struct.pack(">Q", len(aad_bytes) * 8)  # 64-bit big-endian bit length
    mac_input = aad_bytes + iv + ciphertext + al
    computed_tag = hmac.new(mac_key, mac_input, hashlib.sha512).digest()[:32]

    if not hmac.compare_digest(computed_tag, tag):
        raise ValueError("HMAC verification failed — token may be tampered")

    # Decrypt AES-256-CBC
    cipher = Cipher(algorithms.AES(enc_key), modes.CBC(iv))
    decryptor = cipher.decryptor()
    padded_plaintext = decryptor.update(ciphertext) + decryptor.finalize()

    # Remove PKCS7 padding
    unpadder = padding.PKCS7(128).unpadder()
    plaintext = unpadder.update(padded_plaintext) + unpadder.finalize()

    return plaintext


def _decrypt_a256gcm(key: bytes, iv: bytes, ciphertext: bytes, tag: bytes) -> bytes:
    """Decrypt A256GCM (AES-256-GCM) JWE content."""
    # For A256GCM, use the last 32 bytes of the 64-byte derived key
    enc_key = key[32:]
    aesgcm = AESGCM(enc_key)
    return aesgcm.decrypt(iv, ciphertext + tag, None)


def _decrypt_jwe(token: str, key: bytes) -> dict:
    """
    Decrypt a JWE compact serialization token.

    Supports:
      - alg=dir, enc=A256CBC-HS512 (Auth.js v5 default)
      - alg=dir, enc=A256GCM (alternate variant)

    JWE compact format: BASE64URL(header).BASE64URL(encrypted_key).BASE64URL(iv).BASE64URL(ciphertext).BASE64URL(tag)
    """
    parts = token.split(".")
    if len(parts) != 5:
        raise ValueError("Invalid JWE format: expected 5 parts")

    # Parse and verify header
    header = json.loads(_base64url_decode(parts[0]))
    if header.get("alg") != "dir":
        raise ValueError(f"Unsupported JWE algorithm: {header.get('alg')}")

    enc = header.get("enc")
    if enc not in ("A256CBC-HS512", "A256GCM"):
        raise ValueError(f"Unsupported JWE encoding: {enc}")

    # encrypted_key should be empty for dir
    if parts[1]:
        raise ValueError("Unexpected encrypted key in dir JWE")

    iv = _base64url_decode(parts[2])
    ciphertext = _base64url_decode(parts[3])
    tag = _base64url_decode(parts[4])

    if enc == "A256CBC-HS512":
        # AAD is the raw base64url-encoded header (parts[0])
        plaintext = _decrypt_a256cbc_hs512(key, iv, ciphertext, tag, parts[0])
    else:  # A256GCM
        plaintext = _decrypt_a256gcm(key, iv, ciphertext, tag)

    return json.loads(plaintext)


def decode_authjs_token(token: str) -> CurrentUser:
    """
    Decode an Auth.js v5 JWT token.

    Auth.js v5 issues JWE-encrypted tokens by default (alg=dir, enc=A256CBC-HS512).
    Falls back to plain JWS (HS256/384/512) if the token is not encrypted.

    Raises ValueError on invalid or expired tokens.
    """
    key = _derive_encryption_key(settings.AUTH_SECRET)

    # Try JWE decryption first (Auth.js v5 default)
    try:
        payload = _decrypt_jwe(token, key)
    except (ValueError, json.JSONDecodeError, UnicodeDecodeError, Exception):
        # Fall back to JWS verification (if Auth.js configured for signed-only)
        try:
            payload = pyjwt.decode(
                token,
                settings.AUTH_SECRET,
                algorithms=["HS256", "HS384", "HS512"],
            )
        except pyjwt.exceptions.PyJWTError as exc:
            raise ValueError(f"Invalid or expired token: {exc}") from exc

    # Check token expiry
    exp = payload.get("exp")
    if exp and isinstance(exp, (int, float)):
        if time.time() > exp:
            raise ValueError("Token has expired")

    # Auth.js v5 token shape:
    # { "sub": "user-id", "email": "...", "name": "...", "iat": ..., "exp": ... }
    user_id = payload.get("sub")
    email = payload.get("email", "")
    name = payload.get("name", "")

    if not user_id:
        raise ValueError("Token missing 'sub' claim")

    return CurrentUser(user_id=user_id, email=email, name=name)


def verify_token(token: str) -> dict:
    """
    Decode a JWT token and return the raw payload dict.

    Used by WebSocket endpoints that need the payload without
    constructing a full CurrentUser object.
    """
    key = _derive_encryption_key(settings.AUTH_SECRET)

    # Try JWE decryption first (Auth.js v5 default)
    try:
        payload = _decrypt_jwe(token, key)
    except (ValueError, json.JSONDecodeError, UnicodeDecodeError, Exception):
        # Fall back to JWS verification
        try:
            payload = pyjwt.decode(
                token,
                settings.AUTH_SECRET,
                algorithms=["HS256", "HS384", "HS512"],
            )
        except pyjwt.exceptions.PyJWTError as exc:
            raise ValueError(f"Invalid or expired token: {exc}") from exc

    # Check token expiry
    exp = payload.get("exp")
    if exp and isinstance(exp, (int, float)):
        if time.time() > exp:
            raise ValueError("Token has expired")

    return payload
