"""Tests for the settings feature.

Covers: encryption, ProfileStore, ProfileService, and settings API endpoints.
"""

import os
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml
from fastapi.testclient import TestClient

from agent_core.api.server import create_app
from agent_core.config import AgentConfig
from agent_core.models.llm_settings import LlmSettingsFile
from agent_core.models.settings import (
    SettingsCategory,
    UpdateProfileRequest,
    UserProfileRecord,
    UserProfileResponse,
)
from agent_core.persistence.profile_store import ProfileStore
from agent_core.security.encryption import (
    decrypt,
    encrypt,
    generate_key,
    reset_fernet,
)
from agent_core.services.profile_service import ProfileService
from agent_core.tools.blackboard import get_all_ddls

# ===========================================================================
# Fixtures
# ===========================================================================


@pytest.fixture(autouse=True)
def fresh_encryption_key():
    """Generate and use a fresh Fernet key for each test to ensure isolation."""
    key = generate_key()
    reset_fernet(key)
    yield key
    reset_fernet(None)


@pytest.fixture
async def profile_store():
    """In-memory ProfileStore for isolated tests."""
    store = ProfileStore(":memory:")
    await store.initialize()
    try:
        yield store
    finally:
        await store.close()


@pytest.fixture
def client(fresh_encryption_key, tmp_path: Path) -> TestClient:
    """TestClient with a fresh in-memory app (shared encryption key)."""
    os.environ["SETTINGS_ENCRYPTION_KEY"] = fresh_encryption_key
    config = AgentConfig(
        openai_api_key="test-key",
        model_name="gpt-4o-mini",
        db_path=":memory:",
        encryption_key=fresh_encryption_key,
        llm_settings_path=str(tmp_path / "llm_settings.yaml"),
    )
    app = create_app(config)
    with TestClient(app) as c:
        yield c
    del os.environ["SETTINGS_ENCRYPTION_KEY"]


# ===========================================================================
# Encryption module tests
# ===========================================================================


class TestEncryption:
    """Unit tests for the encryption module."""

    def test_encrypt_returns_non_empty_string(self) -> None:
        ciphertext = encrypt("hello")
        assert isinstance(ciphertext, str)
        assert len(ciphertext) > 0

    def test_decrypt_roundtrip(self) -> None:
        plaintext = "sup3r-s3cr3t!"
        assert decrypt(encrypt(plaintext)) == plaintext

    def test_encrypt_empty_returns_empty(self) -> None:
        assert encrypt("") == ""

    def test_decrypt_empty_returns_empty(self) -> None:
        assert decrypt("") == ""

    def test_ciphertext_differs_from_plaintext(self) -> None:
        plaintext = "password123"
        ciphertext = encrypt(plaintext)
        assert ciphertext != plaintext

    def test_different_encryptions_of_same_plaintext_differ(self) -> None:
        # Fernet uses a random IV per call → deterministically different tokens.
        p = "abc"
        assert encrypt(p) != encrypt(p)

    def test_unicode_roundtrip(self) -> None:
        plaintext = "\u5bc6\u7801123\uff01@#"
        assert decrypt(encrypt(plaintext)) == plaintext

    def test_generate_key_is_valid_fernet_key(self) -> None:
        key = generate_key()
        reset_fernet(key)
        assert decrypt(encrypt("test")) == "test"


class TestAppStartupWithoutLlmProvider:
    """Regression tests for app startup with empty LLM settings."""

    def test_app_starts_and_settings_remain_available(self, tmp_path: Path) -> None:
        """The server should boot even before any provider is configured."""
        app = create_app(
            AgentConfig(
                openai_api_key="",
                model_name="gpt-4o-mini",
                db_path=":memory:",
                llm_settings_path=str(tmp_path / "llm_settings.yaml"),
            )
        )

        with TestClient(app) as client:
            health_response = client.get("/health")
            settings_response = client.get("/settings/llm")

        assert health_response.status_code == 200
        assert settings_response.status_code == 200
        assert settings_response.json() == LlmSettingsFile().model_dump()


# ===========================================================================
# SettingsCategory enum tests
# ===========================================================================


class TestSettingsCategory:
    """Tests for the SettingsCategory StrEnum."""

    def test_values(self) -> None:
        assert SettingsCategory.CAS_SERVICE == "cas_service"
        assert SettingsCategory.EMAIL_SERVICE == "email_service"
        assert SettingsCategory.EXTENSION_SERVICE == "extension_service"

    def test_is_string(self) -> None:
        assert isinstance(SettingsCategory.CAS_SERVICE, str)


# ===========================================================================
# ProfileStore tests
# ===========================================================================


class TestProfileStore:
    """Unit tests for ProfileStore."""

    @pytest.mark.asyncio
    async def test_get_profile_default_empty(self, profile_store: ProfileStore) -> None:
        record = await profile_store.get_profile()
        assert record.cas_account == ""
        assert record.cas_password_encrypted == ""
        assert record.email_account == ""
        assert record.email_password_encrypted == ""

    @pytest.mark.asyncio
    async def test_update_cas_account(self, profile_store: ProfileStore) -> None:
        await profile_store.update_profile(cas_account="testuser")
        record = await profile_store.get_profile()
        assert record.cas_account == "testuser"

    @pytest.mark.asyncio
    async def test_update_cas_password_is_encrypted(
        self, profile_store: ProfileStore
    ) -> None:
        await profile_store.update_profile(cas_password="plaintext")
        record = await profile_store.get_profile()
        # Stored value must not be the plaintext
        assert record.cas_password_encrypted != "plaintext"
        assert record.cas_password_encrypted != ""

    @pytest.mark.asyncio
    async def test_decrypt_cas_password(self, profile_store: ProfileStore) -> None:
        await profile_store.update_profile(cas_password="mypassword")
        decrypted = await profile_store.get_decrypted_cas_password()
        assert decrypted == "mypassword"

    @pytest.mark.asyncio
    async def test_update_email_credentials(self, profile_store: ProfileStore) -> None:
        await profile_store.update_profile(
            email_account="user@mail.sustech.edu.cn",
            email_password="emailpw",
        )
        record = await profile_store.get_profile()
        assert record.email_account == "user@mail.sustech.edu.cn"
        assert record.email_password_encrypted != "emailpw"
        decrypted = await profile_store.get_decrypted_email_password()
        assert decrypted == "emailpw"

    @pytest.mark.asyncio
    async def test_partial_update_leaves_other_fields_unchanged(
        self, profile_store: ProfileStore
    ) -> None:
        await profile_store.update_profile(cas_account="user1", cas_password="pw1")
        await profile_store.update_profile(email_account="a@b.com")
        record = await profile_store.get_profile()
        assert record.cas_account == "user1"
        assert await profile_store.get_decrypted_cas_password() == "pw1"
        assert record.email_account == "a@b.com"

    @pytest.mark.asyncio
    async def test_overwrite_updates_in_place(
        self, profile_store: ProfileStore
    ) -> None:
        await profile_store.update_profile(cas_account="old")
        await profile_store.update_profile(cas_account="new")
        record = await profile_store.get_profile()
        assert record.cas_account == "new"

    @pytest.mark.asyncio
    async def test_none_fields_not_updated(self, profile_store: ProfileStore) -> None:
        await profile_store.update_profile(cas_account="keep")
        await profile_store.update_profile(cas_account=None)
        record = await profile_store.get_profile()
        assert record.cas_account == "keep"

    @pytest.mark.asyncio
    async def test_save_and_reload_profile(self, profile_store: ProfileStore) -> None:
        record = UserProfileRecord(
            cas_account="a",
            cas_password_encrypted=encrypt("pw"),
            email_account="e@b.com",
            email_password_encrypted=encrypt("epw"),
        )
        await profile_store.save_profile(record)
        loaded = await profile_store.get_profile()
        assert loaded.cas_account == "a"
        assert loaded.email_account == "e@b.com"

    @pytest.mark.asyncio
    async def test_reset_profile_clears_all_fields(
        self, profile_store: ProfileStore
    ) -> None:
        await profile_store.update_profile(
            cas_account="user",
            cas_password="pw",
            email_account="e@b.com",
            email_password="epw",
        )
        result = await profile_store.reset_profile()
        assert result.cas_account == ""
        assert result.cas_password_encrypted == ""
        assert result.email_account == ""
        assert result.email_password_encrypted == ""

    @pytest.mark.asyncio
    async def test_reset_profile_persists_empty_state(
        self, profile_store: ProfileStore
    ) -> None:
        await profile_store.update_profile(cas_account="user", cas_password="pw")
        await profile_store.reset_profile()
        record = await profile_store.get_profile()
        assert record.cas_account == ""
        assert record.cas_password_encrypted == ""


# ===========================================================================
# Pydantic model tests
# ===========================================================================


class TestPydanticModels:
    """Tests for the settings Pydantic models."""

    def test_user_profile_record_defaults(self) -> None:
        r = UserProfileRecord()
        assert r.cas_account == ""
        assert r.cas_password_encrypted == ""

    def test_user_profile_response_defaults(self) -> None:
        r = UserProfileResponse()
        assert r.cas_password_is_set is False
        assert r.email_password_is_set is False

    def test_update_profile_request_all_none(self) -> None:
        r = UpdateProfileRequest()
        assert r.cas_account is None
        assert r.cas_password is None
        assert r.email_account is None
        assert r.email_password is None

    def test_llm_settings_file_defaults(self) -> None:
        settings = LlmSettingsFile()
        assert settings.temperature == 0.0
        assert settings.max_iterations == 10
        assert settings.providers == []


# ===========================================================================
# Settings API endpoint tests
# ===========================================================================


class TestSettingsEndpoints:
    """Integration tests for /settings endpoints."""

    def test_get_settings_returns_empty_defaults(self, client: TestClient) -> None:
        response = client.get("/settings")
        assert response.status_code == 200
        data = response.json()
        assert data["cas_account"] == ""
        assert data["cas_password_is_set"] is False
        assert data["email_account"] == ""
        assert data["email_password_is_set"] is False

    def test_put_settings_updates_cas_account(self, client: TestClient) -> None:
        response = client.put(
            "/settings",
            json={"cas_account": "student123"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["cas_account"] == "student123"
        assert data["cas_password_is_set"] is False

    def test_put_settings_updates_cas_password_flag(self, client: TestClient) -> None:
        client.put("/settings", json={"cas_password": "secret"})
        response = client.get("/settings")
        data = response.json()
        assert data["cas_password_is_set"] is True

    def test_put_settings_password_not_returned_in_response(
        self, client: TestClient
    ) -> None:
        response = client.put(
            "/settings",
            json={"cas_account": "user", "cas_password": "pw"},
        )
        data = response.json()
        # Must not contain plaintext password or ciphertext
        assert "cas_password" not in data
        assert "cas_password_encrypted" not in data

    def test_put_settings_email_credentials(self, client: TestClient) -> None:
        response = client.put(
            "/settings",
            json={
                "email_account": "test@mail.sustech.edu.cn",
                "email_password": "emailpw",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["email_account"] == "test@mail.sustech.edu.cn"
        assert data["email_password_is_set"] is True

    def test_put_settings_partial_update_preserves_other_fields(
        self, client: TestClient
    ) -> None:
        client.put("/settings", json={"cas_account": "u1", "cas_password": "p1"})
        client.put("/settings", json={"email_account": "e@b.com"})
        response = client.get("/settings")
        data = response.json()
        assert data["cas_account"] == "u1"
        assert data["cas_password_is_set"] is True
        assert data["email_account"] == "e@b.com"

    def test_put_settings_clear_field_with_empty_string(
        self, client: TestClient
    ) -> None:
        # Setting account to empty string explicitly clears it
        client.put("/settings", json={"cas_account": "user"})
        client.put("/settings", json={"cas_account": ""})
        response = client.get("/settings")
        data = response.json()
        assert data["cas_account"] == ""

    def test_get_settings_response_schema(self, client: TestClient) -> None:
        response = client.get("/settings")
        data = response.json()
        required_keys = {
            "cas_account",
            "cas_password_is_set",
            "email_account",
            "email_password_is_set",
        }
        assert required_keys.issubset(data.keys())

    def test_delete_settings_resets_all_fields(self, client: TestClient) -> None:
        # Populate some data first
        client.put(
            "/settings",
            json={
                "cas_account": "user",
                "cas_password": "pw",
                "email_account": "e@b.com",
                "email_password": "epw",
            },
        )
        # Reset
        response = client.delete("/settings")
        assert response.status_code == 200
        data = response.json()
        assert data["cas_account"] == ""
        assert data["cas_password_is_set"] is False
        assert data["email_account"] == ""
        assert data["email_password_is_set"] is False

    def test_delete_settings_get_confirms_empty(self, client: TestClient) -> None:
        client.put("/settings", json={"cas_account": "user", "cas_password": "pw"})
        client.delete("/settings")
        response = client.get("/settings")
        data = response.json()
        assert data["cas_account"] == ""
        assert data["cas_password_is_set"] is False

    def test_get_llm_settings_returns_defaults(self, client: TestClient) -> None:
        response = client.get("/settings/llm")
        assert response.status_code == 200
        data = response.json()
        assert data["temperature"] == 0.0
        assert data["max_iterations"] == 10
        assert data["providers"] == []

    def test_put_llm_settings_persists_yaml_backed_config(
        self, client: TestClient
    ) -> None:
        response = client.put(
            "/settings/llm",
            json={
                "temperature": 0.4,
                "max_iterations": 6,
                "system_prompt": "Configured prompt",
                "providers": [
                    {
                        "id": "backup",
                        "name": "Backup",
                        "priority": 1,
                        "base_url": "https://backup.example/v1",
                        "api_key": "backup-key",
                        "model": "backup-model",
                        "enabled": True,
                    },
                    {
                        "id": "primary",
                        "name": "Primary",
                        "priority": 0,
                        "base_url": "https://primary.example/v1",
                        "api_key": "primary-key",
                        "model": "primary-model",
                        "enabled": True,
                    },
                ],
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["providers"][0]["id"] == "primary"
        assert data["providers"][1]["id"] == "backup"

        get_response = client.get("/settings/llm")
        get_data = get_response.json()
        assert get_data["system_prompt"] == "Configured prompt"
        assert get_data["providers"][0]["api_key"] == "primary-key"

    def test_put_llm_settings_invalid_enabled_provider_returns_422(
        self, client: TestClient
    ) -> None:
        response = client.put(
            "/settings/llm",
            json={
                "temperature": 0.4,
                "max_iterations": 6,
                "providers": [
                    {
                        "id": "primary",
                        "name": "Primary",
                        "priority": 0,
                        "base_url": "https://primary.example/v1",
                        "api_key": "",
                        "model": "primary-model",
                        "enabled": True,
                    }
                ],
            },
        )

        assert response.status_code == 422
        detail = response.json()["detail"]
        assert any("has no API key" in str(item) for item in detail)

    def test_put_llm_settings_unexpected_failure_returns_500(
        self, client: TestClient
    ) -> None:
        with patch(
            "agent_core.api.routes.settings.save_llm_settings",
            side_effect=RuntimeError("boom"),
        ):
            response = client.put(
                "/settings/llm",
                json={
                    "temperature": 0.4,
                    "max_iterations": 6,
                    "providers": [],
                },
            )

        assert response.status_code == 500
        assert response.json() == {"detail": "Failed to update LLM settings"}

    def test_get_llm_settings_normalizes_malformed_provider_ids(
        self, fresh_encryption_key: str, tmp_path: Path
    ) -> None:
        llm_settings_path = tmp_path / "llm_settings.yaml"
        llm_settings_path.write_text(
            yaml.safe_dump(
                {
                    "temperature": 0.1,
                    "max_iterations": 5,
                    "system_prompt": "Prompt",
                    "providers": [
                        {
                            "id": " legacy_provider ",
                            "name": "Primary",
                            "priority": 0,
                            "base_url": "https://primary.example/v1",
                            "api_key": "primary-key",
                            "model": "primary-model",
                            "enabled": True,
                        },
                        {
                            "id": "legacy_provider",
                            "name": "Backup",
                            "priority": 1,
                            "base_url": "https://backup.example/v1",
                            "api_key": "backup-key",
                            "model": "backup-model",
                            "enabled": True,
                        },
                    ],
                },
                sort_keys=False,
            ),
            encoding="utf-8",
        )

        os.environ["SETTINGS_ENCRYPTION_KEY"] = fresh_encryption_key
        app = create_app(
            AgentConfig(
                openai_api_key="test-key",
                model_name="gpt-4o-mini",
                db_path=":memory:",
                encryption_key=fresh_encryption_key,
                llm_settings_path=str(llm_settings_path),
            )
        )

        with TestClient(app) as client:
            response = client.get("/settings/llm")

        del os.environ["SETTINGS_ENCRYPTION_KEY"]

        assert response.status_code == 200
        data = response.json()
        assert data["providers"][0]["id"] == "legacy_provider"
        assert data["providers"][1]["id"] == "provider_2"

    def test_put_llm_settings_clears_stale_session_provider_preferences(
        self, client: TestClient
    ) -> None:
        create_response = client.post(
            "/sessions", json={"title": "Session With Provider"}
        )
        session_id = create_response.json()["id"]

        preferences_response = client.patch(
            f"/sessions/{session_id}/preferences",
            json={
                "selected_provider_id": " legacy_provider ",
                "fallback_mode": "manual",
            },
        )
        assert preferences_response.status_code == 200

        response = client.put(
            "/settings/llm",
            json={
                "temperature": 0.4,
                "max_iterations": 6,
                "system_prompt": "Configured prompt",
                "providers": [
                    {
                        "id": "legacy_provider",
                        "name": "Primary",
                        "priority": 0,
                        "base_url": "https://primary.example/v1",
                        "api_key": "primary-key",
                        "model": "primary-model",
                        "enabled": True,
                    }
                ],
            },
        )

        assert response.status_code == 200

        session_response = client.get(f"/sessions/{session_id}")
        assert session_response.status_code == 200
        assert session_response.json()["session"]["selected_provider_id"] is None

    def test_delete_llm_settings_resets_defaults(self, client: TestClient) -> None:
        client.put(
            "/settings/llm",
            json={
                "temperature": 0.4,
                "max_iterations": 6,
                "system_prompt": "Configured prompt",
                "providers": [
                    {
                        "id": "primary",
                        "name": "Primary",
                        "priority": 0,
                        "base_url": "",
                        "api_key": "primary-key",
                        "model": "primary-model",
                        "enabled": True,
                    }
                ],
            },
        )
        response = client.delete("/settings/llm")
        assert response.status_code == 200
        data = response.json()
        assert data["temperature"] == 0.0
        assert data["max_iterations"] == 10
        assert data["providers"] == []


# ===========================================================================
# ProfileService tests
# ===========================================================================


@pytest.fixture
async def profile_service(profile_store: ProfileStore) -> ProfileService:
    """ProfileService backed by an in-memory ProfileStore."""
    return ProfileService(profile_store)


class TestProfileService:
    """Unit tests for ProfileService."""

    @pytest.mark.asyncio
    async def test_get_profile_returns_response_model(
        self, profile_service: ProfileService
    ) -> None:
        result = await profile_service.get_profile()
        assert isinstance(result, UserProfileResponse)
        assert result.cas_account == ""
        assert result.cas_password_is_set is False
        assert result.email_account == ""
        assert result.email_password_is_set is False

    @pytest.mark.asyncio
    async def test_update_profile_cas_account(
        self, profile_service: ProfileService
    ) -> None:
        request = UpdateProfileRequest(cas_account="student123")
        result = await profile_service.update_profile(request)
        assert result.cas_account == "student123"
        assert result.cas_password_is_set is False

    @pytest.mark.asyncio
    async def test_update_profile_sets_password_flag(
        self, profile_service: ProfileService
    ) -> None:
        request = UpdateProfileRequest(cas_password="secret")
        result = await profile_service.update_profile(request)
        assert result.cas_password_is_set is True

    @pytest.mark.asyncio
    async def test_update_profile_password_not_in_response(
        self, profile_service: ProfileService
    ) -> None:
        request = UpdateProfileRequest(cas_account="u", cas_password="pw")
        result = await profile_service.update_profile(request)
        # UserProfileResponse has no password fields
        result_dict = result.model_dump()
        assert "cas_password" not in result_dict
        assert "cas_password_encrypted" not in result_dict

    @pytest.mark.asyncio
    async def test_update_profile_partial_preserves_other_fields(
        self, profile_service: ProfileService
    ) -> None:
        await profile_service.update_profile(
            UpdateProfileRequest(cas_account="u1", cas_password="p1")
        )
        await profile_service.update_profile(
            UpdateProfileRequest(email_account="e@b.com")
        )
        result = await profile_service.get_profile()
        assert result.cas_account == "u1"
        assert result.cas_password_is_set is True
        assert result.email_account == "e@b.com"

    @pytest.mark.asyncio
    async def test_reset_profile_clears_all(
        self, profile_service: ProfileService
    ) -> None:
        await profile_service.update_profile(
            UpdateProfileRequest(
                cas_account="u",
                cas_password="p",
                email_account="e@b.com",
                email_password="ep",
            )
        )
        result = await profile_service.reset_profile()
        assert result.cas_account == ""
        assert result.cas_password_is_set is False
        assert result.email_account == ""
        assert result.email_password_is_set is False

    @pytest.mark.asyncio
    async def test_reset_profile_persists(
        self, profile_service: ProfileService
    ) -> None:
        await profile_service.update_profile(
            UpdateProfileRequest(cas_account="u", cas_password="p")
        )
        await profile_service.reset_profile()
        result = await profile_service.get_profile()
        assert result.cas_account == ""
        assert result.cas_password_is_set is False

    @pytest.mark.asyncio
    async def test_blackboard_via_profile(
        self, profile_service: ProfileService
    ) -> None:
        await profile_service.update_profile(
            UpdateProfileRequest(
                cas_account="mock_user_name", cas_password="mock_pass_word"
            )
        )
        all_ddls = await get_all_ddls(profile_service)
        assert isinstance(all_ddls, dict)
        assert "Mock Course" in all_ddls
        assert isinstance(all_ddls["Mock Course"], list)
        assert all_ddls["Mock Course"][0]["title"] == "Mock Assignment 1"
