"""Profile management service — single source of truth for user credential logic.

Encapsulates all business operations on the user profile (CAS and email
credentials).  Both the REST API controller and any future tool functions
should delegate to this service so that logic is defined in exactly one place.

Architecture note (Controller–Service–Store layers):
  - Controller (routes/settings.py): HTTP binding, request/response shaping
  - Service (this file):             business operations, response construction
  - Store (profile_store.py):        pure DB persistence, no business logic
"""

from agent_core.logging_utils import get_logger
from agent_core.models.settings import UpdateProfileRequest, UserProfileResponse
from agent_core.persistence.profile_store import ProfileStore

logger = get_logger("services.profile")


def _to_response(
    record_cas_account: str, cas_pw_enc: str, email_account: str, email_pw_enc: str
) -> UserProfileResponse:
    """Build a sanitised :class:`UserProfileResponse` from raw profile fields.

    Passwords are **never** included in the response — only boolean flags.

    Args:
        record_cas_account: The CAS account string.
        cas_pw_enc: The encrypted CAS password ciphertext (may be empty).
        email_account: The email account string.
        email_pw_enc: The encrypted email password ciphertext (may be empty).

    Returns:
        A :class:`~agent_core.models.settings.UserProfileResponse` with
        boolean password flags.
    """
    return UserProfileResponse(
        cas_account=record_cas_account,
        cas_password_is_set=bool(cas_pw_enc),
        email_account=email_account,
        email_password_is_set=bool(email_pw_enc),
    )


class ProfileService:
    """Service layer for user profile (settings) operations.

    Mediates between the REST API controller and the :class:`ProfileStore`,
    handling response construction and providing a single entry point for
    all profile business operations.

    Attributes:
        _store: The underlying :class:`ProfileStore` for persistence.
    """

    def __init__(self, store: ProfileStore) -> None:
        """Initialise the service with a ProfileStore.

        Args:
            store: Initialised :class:`ProfileStore` instance.
        """
        self._store = store

    async def get_profile(self) -> UserProfileResponse:
        """Return the current user profile as a sanitised API response.

        Passwords are **never** returned — only boolean flags indicate
        whether each password has been configured.

        Returns:
            Sanitised :class:`~agent_core.models.settings.UserProfileResponse`.
        """
        record = await self._store.get_profile()
        return _to_response(
            record.cas_account,
            record.cas_password_encrypted,
            record.email_account,
            record.email_password_encrypted,
        )

    async def get_decrypted_profile(self) -> tuple[str, str]:
        """Return the current user profile as a tuple.

        Returns:
            A tuple containing the CAS account and decrypted CAS password.
        """
        record = await self._store.get_profile()
        cas_pw = await self._store.get_decrypted_cas_password()
        return record.cas_account, cas_pw

    async def update_profile(
        self, request: UpdateProfileRequest
    ) -> UserProfileResponse:
        """Apply a partial update and return the updated sanitised response.

        Only non-``None`` fields in *request* are modified.  Plaintext
        passwords are encrypted by the Store before being persisted.

        Args:
            request: Partial update with plaintext credentials.

        Returns:
            Sanitised :class:`~agent_core.models.settings.UserProfileResponse`
            reflecting the post-update state.
        """
        updated = await self._store.update_profile(
            cas_account=request.cas_account,
            cas_password=request.cas_password,
            email_account=request.email_account,
            email_password=request.email_password,
        )
        return _to_response(
            updated.cas_account,
            updated.cas_password_encrypted,
            updated.email_account,
            updated.email_password_encrypted,
        )

    async def reset_profile(self) -> UserProfileResponse:
        """Reset the user profile to an empty state and return the result.

        Clears all stored credentials (CAS and email accounts and passwords).

        Returns:
            Sanitised :class:`~agent_core.models.settings.UserProfileResponse`
            reflecting the cleared state (all fields empty / flags false).
        """
        record = await self._store.reset_profile()
        return _to_response(
            record.cas_account,
            record.cas_password_encrypted,
            record.email_account,
            record.email_password_encrypted,
        )
