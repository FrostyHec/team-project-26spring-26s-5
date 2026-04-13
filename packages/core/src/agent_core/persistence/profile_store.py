"""SQLite-backed persistence for user profile (settings) data.

Stores a single logical user profile row in the ``user_profile`` table.
All password values are stored encrypted by the
:mod:`agent_core.security.encryption` module; this layer handles the
encrypt/decrypt calls transparently.

Usage::

    store = ProfileStore(":memory:")
    await store.initialize()
    record = await store.get_profile()
    await store.save_profile(record.model_copy(update={"cas_account": "myuser"}))
    await store.close()
"""

from enum import StrEnum
from pathlib import Path

import aiosqlite

from agent_core.logging_utils import get_logger
from agent_core.models.settings import UserProfileRecord
from agent_core.security.encryption import decrypt, encrypt

logger = get_logger("persistence.profile")

# ---------- Schema ----------

_PROFILE_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS user_profile (
    key    TEXT PRIMARY KEY,
    value  TEXT NOT NULL DEFAULT ''
);
"""

# ---------- Storage key constants ----------


class _ProfileKey(StrEnum):
    """Internal SQLite row keys for the user_profile table.

    Inherits from :class:`~enum.StrEnum` so each member can be used directly
    wherever a plain ``str`` is expected (e.g. as a SQL parameter).
    """

    CAS_ACCOUNT = "cas_account"
    CAS_PASSWORD_ENCRYPTED = "cas_password_encrypted"
    EMAIL_ACCOUNT = "email_account"
    EMAIL_PASSWORD_ENCRYPTED = "email_password_encrypted"


class ProfileStore:
    """Async SQLite store for user profile settings.

    One row per logical field using a simple key/value schema.  Passwords
    are stored encrypted; the store calls :func:`encrypt` and :func:`decrypt`
    automatically.

    Attributes:
        db_path: Path to the SQLite file (may be ``':memory:'`` for tests).
    """

    def __init__(self, db_path: str = "sessions.db") -> None:
        """Initialise the store.

        Args:
            db_path: SQLite database path.  Shares the same DB file as the
                :class:`~agent_core.persistence.session_store.SessionStore`
                by default.
        """
        self.db_path = db_path
        self._db: aiosqlite.Connection | None = None

    async def initialize(self) -> None:
        """Open the database and create the ``user_profile`` table if needed."""
        if self.db_path != ":memory:":
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._db = await aiosqlite.connect(self.db_path)
        self._db.row_factory = aiosqlite.Row
        await self._db.executescript(_PROFILE_SCHEMA_SQL)
        await self._db.commit()
        logger.info("Profile store initialized at %s", self.db_path)

    async def close(self) -> None:
        """Close the database connection."""
        if self._db:
            await self._db.close()
            self._db = None

    @property
    def db(self) -> aiosqlite.Connection:
        """Active database connection.

        Raises:
            RuntimeError: If :meth:`initialize` has not been called.
        """
        if self._db is None:
            raise RuntimeError("ProfileStore not initialized — call initialize() first")
        return self._db

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _get(self, key: str) -> str:
        """Retrieve a single value from the profile table.

        Args:
            key: The profile key name.

        Returns:
            The stored value, or an empty string if absent.
        """
        async with self.db.execute(
            "SELECT value FROM user_profile WHERE key = ?", (key,)
        ) as cursor:
            row = await cursor.fetchone()
            return row["value"] if row else ""

    async def _set(self, key: str, value: str) -> None:
        """Upsert a key/value pair in the profile table.

        Args:
            key: The profile key name.
            value: The value to store.
        """
        await self.db.execute(
            "INSERT INTO user_profile (key, value) VALUES (?, ?)"
            " ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def get_profile(self) -> UserProfileRecord:
        """Load the current user profile from the database.

        Password fields are returned as **encrypted** ciphertext (as stored in
        the database).  Callers that need the plaintext should use
        :meth:`get_decrypted_cas_password` or
        :meth:`get_decrypted_email_password` instead.

        Returns:
            The current :class:`~agent_core.models.settings.UserProfileRecord`
            with encrypted password fields.
        """
        cas_account = await self._get(_ProfileKey.CAS_ACCOUNT)
        cas_pw_enc = await self._get(_ProfileKey.CAS_PASSWORD_ENCRYPTED)
        email_account = await self._get(_ProfileKey.EMAIL_ACCOUNT)
        email_pw_enc = await self._get(_ProfileKey.EMAIL_PASSWORD_ENCRYPTED)

        return UserProfileRecord(
            cas_account=cas_account,
            cas_password_encrypted=cas_pw_enc,
            email_account=email_account,
            email_password_encrypted=email_pw_enc,
        )

    async def save_profile(self, record: UserProfileRecord) -> None:
        """Persist the user profile to the database.

        Password fields stored in the record must already be **encrypted**;
        use :meth:`update_profile` if you have plaintext values.

        Args:
            record: The profile to persist.
        """
        await self._set(_ProfileKey.CAS_ACCOUNT, record.cas_account)
        await self._set(
            _ProfileKey.CAS_PASSWORD_ENCRYPTED, record.cas_password_encrypted
        )
        await self._set(_ProfileKey.EMAIL_ACCOUNT, record.email_account)
        await self._set(
            _ProfileKey.EMAIL_PASSWORD_ENCRYPTED, record.email_password_encrypted
        )
        await self.db.commit()

    async def update_profile(
        self,
        *,
        cas_account: str | None = None,
        cas_password: str | None = None,
        email_account: str | None = None,
        email_password: str | None = None,
    ) -> UserProfileRecord:
        """Apply partial updates to the user profile.

        Only non-``None`` fields are modified.  Plaintext passwords are
        **encrypted** automatically before being written to the database.

        Args:
            cas_account: New CAS username, or ``None`` to leave unchanged.
            cas_password: New plaintext CAS password, or ``None`` to leave
                unchanged.
            email_account: New enterprise email address.
            email_password: New plaintext email password.

        Returns:
            The updated (encrypted)
            :class:`~agent_core.models.settings.UserProfileRecord`.
        """
        current = await self.get_profile()

        updated = current.model_copy(
            update={
                k: v
                for k, v in {
                    _ProfileKey.CAS_ACCOUNT: cas_account,
                    _ProfileKey.EMAIL_ACCOUNT: email_account,
                }.items()
                if v is not None
            }
        )

        # Encrypt passwords if provided
        if cas_password is not None:
            updated = updated.model_copy(
                update={_ProfileKey.CAS_PASSWORD_ENCRYPTED: encrypt(cas_password)}
            )
        if email_password is not None:
            updated = updated.model_copy(
                update={_ProfileKey.EMAIL_PASSWORD_ENCRYPTED: encrypt(email_password)}
            )

        await self.save_profile(updated)
        return updated

    async def get_decrypted_cas_password(self) -> str:
        """Retrieve and decrypt the stored CAS password.

        Returns:
            The decrypted CAS password, or an empty string if not set.
        """
        ciphertext = await self._get(_ProfileKey.CAS_PASSWORD_ENCRYPTED)
        return decrypt(ciphertext)

    async def get_decrypted_email_password(self) -> str:
        """Retrieve and decrypt the stored email password.

        Returns:
            The decrypted email password, or an empty string if not set.
        """
        ciphertext = await self._get(_ProfileKey.EMAIL_PASSWORD_ENCRYPTED)
        return decrypt(ciphertext)

    async def reset_profile(self) -> UserProfileRecord:
        """Reset the user profile to its initial (empty) state.

        Clears all stored credentials (account names and encrypted
        passwords) and returns the resulting empty profile.

        Returns:
            An empty :class:`~agent_core.models.settings.UserProfileRecord`.
        """
        empty = UserProfileRecord()
        await self.save_profile(empty)
        return empty
