"""Pydantic models for user profile settings.

Provides structured types for the CAS (SUSTech SSO), email service,
and extension service credentials stored in the user profile.
Passwords are **always stored encrypted**; this module defines the
public-facing (plaintext) shapes used by the API layer, while the
persistence layer handles encryption/decryption transparently.
"""

from enum import StrEnum

from pydantic import BaseModel

# ---------- Enums ----------


class SettingsCategory(StrEnum):
    """Logical grouping of user-profile settings.

    Attributes:
        CAS_SERVICE: SUSTech CAS (Central Authentication Service) credentials.
        EMAIL_SERVICE: Enterprise email account credentials.
        EXTENSION_SERVICE: Placeholder for future third-party integrations.
    """

    CAS_SERVICE = "cas_service"
    EMAIL_SERVICE = "email_service"
    EXTENSION_SERVICE = "extension_service"


# ---------- Internal storage model ----------


class UserProfileRecord(BaseModel):
    """Complete user profile as stored in the database.

    All password-equivalent fields contain **encrypted** ciphertext.
    This model should never be returned directly from an API endpoint;
    use :class:`UserProfileResponse` for external consumption.

    Attributes:
        cas_account: SUSTech CAS username (plaintext, not sensitive).
        cas_password_encrypted: AES-encrypted CAS password ciphertext.
        email_account: Enterprise email address (plaintext).
        email_password_encrypted: AES-encrypted email password ciphertext.
    """

    cas_account: str = ""
    cas_password_encrypted: str = ""
    email_account: str = ""
    email_password_encrypted: str = ""


# ---------- API response model ----------


class UserProfileResponse(BaseModel):
    """Sanitised user profile returned by the settings API.

    Passwords are **never** included in the response — only a boolean
    flag indicating whether they have been configured.

    Attributes:
        cas_account: SUSTech CAS username.
        cas_password_is_set: True if a CAS password has been stored.
        email_account: Enterprise email address.
        email_password_is_set: True if an email password has been stored.
    """

    cas_account: str = ""
    cas_password_is_set: bool = False
    email_account: str = ""
    email_password_is_set: bool = False


# ---------- API request model ----------


class UpdateProfileRequest(BaseModel):
    """Request body for the PUT /settings endpoint.

    All fields are optional — only supplied fields are updated.  An empty
    string for a password field is treated as "clear this credential".

    Attributes:
        cas_account: New CAS username (or ``None`` to leave unchanged).
        cas_password: New CAS password in plaintext (or ``None`` to leave
            unchanged; empty string to clear).
        email_account: New enterprise email address.
        email_password: New email password in plaintext.
    """

    cas_account: str | None = None
    cas_password: str | None = None
    email_account: str | None = None
    email_password: str | None = None
