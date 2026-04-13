"""Fernet (AES-128-CBC + HMAC-SHA256) symmetric encryption.

Encrypts sensitive settings values.

Uses the ``cryptography`` library's :class:`~cryptography.fernet.Fernet`
implementation, which provides authenticated encryption with automatic IV
generation and ciphertext integrity verification.

The encryption key is sourced from the ``SETTINGS_ENCRYPTION_KEY`` environment
variable (a URL-safe base64-encoded Fernet key, 32 bytes of entropy).  If the
variable is absent at runtime, a fresh key is generated per-process; in
production, always configure ``SETTINGS_ENCRYPTION_KEY`` explicitly.

Public surface
--------------
:data:`ENV_KEY`
    Name of the environment variable holding the Fernet key.
encrypt(plaintext: str) -> str
    Encrypt a UTF-8 string and return a URL-safe base64-encoded token.
decrypt(ciphertext: str) -> str
    Decrypt a token produced by :func:`encrypt` and return the original string.
reset_fernet(key_b64: str | None = None) -> None
    Reset the cached Fernet instance (primarily for testing).
generate_key() -> str
    Generate a new random Fernet key.
"""

import os

from cryptography.fernet import Fernet

# ---------- Constants ----------

#: Environment variable name that holds the Fernet encryption key.
ENV_KEY = "SETTINGS_ENCRYPTION_KEY"
# Internal alias for backwards compatibility within this module.
_ENV_KEY = ENV_KEY

# Module-level cached Fernet instance (lazy-initialized).
_fernet: Fernet | None = None


# ---------- Internal helpers ----------


def _load_or_generate_key() -> bytes:
    """Load the Fernet key from the environment, or generate a new one.

    Returns:
        A URL-safe base64-encoded 32-byte Fernet key.
    """
    raw = os.getenv(_ENV_KEY, "")
    if raw:
        return raw.encode()
    # Generate a fresh key — deterministic within a process but NOT persisted.
    # In production, set SETTINGS_ENCRYPTION_KEY in the environment.
    return Fernet.generate_key()


def _get_fernet() -> Fernet:
    """Return the module-level cached Fernet instance.

    Initializes the instance on first call.

    Returns:
        Configured Fernet cipher.
    """
    global _fernet
    if _fernet is None:
        _fernet = Fernet(_load_or_generate_key())
    return _fernet


# ---------- Public API ----------


def encrypt(plaintext: str) -> str:
    """Encrypt a UTF-8 string using AES-128-CBC (Fernet).

    Args:
        plaintext: The string to encrypt.

    Returns:
        A URL-safe base64-encoded ciphertext token (str).
    """
    if not plaintext:
        return ""
    token: bytes = _get_fernet().encrypt(plaintext.encode())
    return token.decode()


def decrypt(ciphertext: str) -> str:
    """Decrypt a token produced by :func:`encrypt`.

    Args:
        ciphertext: The base64-encoded token to decrypt.

    Returns:
        The original plaintext string.

    Raises:
        cryptography.fernet.InvalidToken: If the token is corrupt or
            was encrypted with a different key.
    """
    if not ciphertext:
        return ""
    plaintext: bytes = _get_fernet().decrypt(ciphertext.encode())
    return plaintext.decode()


def reset_fernet(key_b64: str | None = None) -> None:
    """Reset the cached Fernet instance (primarily for testing).

    Args:
        key_b64: Optional explicit key. If provided it is also written to
            the environment variable so subsequent calls pick it up.
    """
    global _fernet
    if key_b64 is not None:
        os.environ[_ENV_KEY] = key_b64
    _fernet = None


def generate_key() -> str:
    """Generate a new random Fernet key suitable for use as SETTINGS_ENCRYPTION_KEY.

    Returns:
        A URL-safe base64-encoded Fernet key string.
    """
    return Fernet.generate_key().decode()
