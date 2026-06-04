"""
Input validation and sanitization — centralized validation utilities.

Implements TRD §9.2 input validation:
  - Max 4096 chars for text inputs
  - File type whitelist
  - URL scheme whitelist (SSRF protection)
  - HTML/script tag stripping
  - Unicode normalization
"""

from __future__ import annotations

import html
import ipaddress
import re
import socket
import unicodedata
from urllib.parse import urlparse

from fastapi import HTTPException, status

# ── Constants ─────────────────────────────────────────────────────────

MAX_QUERY_LENGTH = 4096
MAX_TEXT_INPUT_LENGTH = 10000
MAX_TITLE_LENGTH = 500

ALLOWED_FILE_EXTENSIONS = {
    ".pdf",
    ".txt",
    ".md",
    ".docx",
    ".doc",
    ".pptx",
    ".ppt",
    ".xlsx",
    ".xls",
    ".csv",
    ".html",
}

ALLOWED_URL_SCHEMES = {"http", "https"}

# Patterns for prompt injection detection
_INJECTION_PATTERNS = [
    re.compile(
        r"(ignore|forget|disregard)\s+(all\s+)?(previous|above|prior)\s+(instructions|prompts|rules)",
        re.IGNORECASE,
    ),
    re.compile(r"you\s+are\s+now\s+(a|an)\s+", re.IGNORECASE),
    re.compile(r"system\s*:\s*", re.IGNORECASE),
    re.compile(r"<\s*script", re.IGNORECASE),
    re.compile(r"javascript\s*:", re.IGNORECASE),
]

# MIME types for file validation
try:
    import magic

    _MAGIC_AVAILABLE = True
except ImportError:
    _MAGIC_AVAILABLE = False

ALLOWED_MIME_TYPES = {
    "application/pdf",
    "text/plain",
    "text/markdown",
    "text/html",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "application/vnd.ms-powerpoint",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.ms-excel",
    "text/csv",
}


# ── Text Sanitization ─────────────────────────────────────────────────


def sanitize_text(text: str, *, max_length: int | None = None) -> str:
    """
    Sanitize a text input: normalize Unicode, strip HTML, enforce length.

    Args:
        text: Raw input text.
        max_length: Maximum allowed length (defaults to MAX_TEXT_INPUT_LENGTH).

    Returns:
        Sanitized text.

    Raises:
        HTTPException(422) if text exceeds max length after sanitization.
    """
    effective_max = max_length or MAX_TEXT_INPUT_LENGTH

    # Unicode normalization (NFC)
    text = unicodedata.normalize("NFC", text)

    # Strip HTML tags
    text = re.sub(r"<[^>]+>", "", text)

    # Decode HTML entities
    text = html.unescape(text)

    # Strip control characters (except newlines and tabs)
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)

    # Enforce length
    if len(text) > effective_max:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Text exceeds maximum length of {effective_max} characters",
        )

    return text.strip()


def validate_query(query: str) -> str:
    """
    Validate and sanitize a chat query.

    Args:
        query: Raw user query.

    Returns:
        Sanitized query string.

    Raises:
        HTTPException(422) for empty or too-long queries.
    """
    query = sanitize_text(query, max_length=MAX_QUERY_LENGTH)

    if not query:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Query cannot be empty",
        )

    return query


def validate_title(title: str) -> str:
    """Validate and sanitize a title/name field."""
    return sanitize_text(title, max_length=MAX_TITLE_LENGTH)


# ── File Validation ───────────────────────────────────────────────────


def validate_file_extension(filename: str) -> str:
    """
    Validate that a filename has an allowed extension.

    Args:
        filename: The uploaded filename.

    Returns:
        The lowercase extension.

    Raises:
        HTTPException(422) for disallowed file types.
    """
    ext = ""
    if "." in filename:
        ext = "." + filename.rsplit(".", 1)[-1].lower()

    if ext not in ALLOWED_FILE_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"File type '{ext}' not allowed. "
                f"Supported types: {', '.join(sorted(ALLOWED_FILE_EXTENSIONS))}"
            ),
        )

    return ext


def validate_file_size(size_bytes: int, *, max_mb: int | None = None) -> None:
    """
    Validate file size against the upload limit.

    Raises:
        HTTPException(413) if file exceeds the limit.
    """
    from app.config import settings

    max_bytes = (max_mb or settings.UPLOAD_MAX_FILE_SIZE_MB) * 1024 * 1024

    if size_bytes > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File size {size_bytes} exceeds limit of {max_bytes} bytes",
        )


# ── URL Validation ────────────────────────────────────────────────────


def validate_url(url: str) -> str:
    """
    Validate a URL for SSRF protection.

    Checks:
      - Scheme must be http or https
      - No private/internal IP ranges (hostname check)
      - No private/internal IP ranges (DNS resolution check for rebinding protection)

    Args:
        url: The URL to validate.

    Returns:
        The validated URL.

    Raises:
        HTTPException(422) for invalid or dangerous URLs.
    """
    parsed = urlparse(url)

    if parsed.scheme not in ALLOWED_URL_SCHEMES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"URL scheme '{parsed.scheme}' not allowed. Use http or https.",
        )

    hostname = parsed.hostname or ""

    # Block localhost and common internal addresses (hostname string check)
    blocked_patterns = [
        "localhost",
        "127.0.0.1",
        "0.0.0.0",
        "::1",
        "fe80:",
        "169.254.",
        "10.",
        "172.16.",
        "172.17.",
        "192.168.",
        "metadata.google",
        "169.254.169.254",  # cloud metadata
    ]

    for pattern in blocked_patterns:
        if hostname.lower().startswith(pattern) or hostname == pattern:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"URL host '{hostname}' is not allowed (SSRF protection)",
            )

    # DNS rebinding protection: resolve hostname and validate actual IP
    try:
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        resolved_ips = socket.getaddrinfo(hostname, port, socket.AF_UNSPEC, socket.SOCK_STREAM)
        for family, _, _, _, sockaddr in resolved_ips:
            ip = sockaddr[0]
            try:
                addr = ipaddress.ip_address(ip)
                if addr.is_private or addr.is_loopback or addr.is_link_local or addr.is_reserved:
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                        detail=(
                            f"URL resolves to private/internal IP {ip} (DNS rebinding protection)"
                        ),
                    )
            except ValueError:
                # Not an IP address, skip
                continue
    except socket.gaierror:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Cannot resolve hostname '{hostname}'",
        )

    return url


# ── Prompt Injection Detection ────────────────────────────────────────


def detect_prompt_injection(text: str) -> list[str]:
    """
    Check text for common prompt injection patterns.

    Returns a list of matched patterns (empty if no injection detected).
    Does NOT raise exceptions — the caller decides how to handle.
    """
    matches: list[str] = []
    for pattern in _INJECTION_PATTERNS:
        if pattern.search(text):
            matches.append(pattern.pattern)
    return matches


def block_prompt_injection(text: str) -> None:
    """Raise HTTPException(400) if prompt injection patterns are detected."""
    matches = detect_prompt_injection(text)
    if matches:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "Prompt injection detected",
                "patterns": [p.pattern for p in matches],
            },
        )


def validate_file_mime_type(file_bytes: bytes) -> str:
    """
    Validate that a file's actual MIME type is allowed.

    Args:
        file_bytes: The file content as bytes.

    Returns:
        The detected MIME type.

    Raises:
        HTTPException(422) if MIME type is not allowed or python-magic is not available.
    """
    if not _MAGIC_AVAILABLE:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="MIME type validation not available — install python-magic package",
        )

    mime = magic.from_buffer(file_bytes, mime=True)
    if mime not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"MIME type '{mime}' not allowed. "
                f"Supported types: {', '.join(sorted(ALLOWED_MIME_TYPES))}"
            ),
        )
    return mime
