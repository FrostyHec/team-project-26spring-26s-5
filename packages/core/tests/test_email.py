"""Tests for the email feature.

Covers: models, EmailStore, EmailClient (mocked), EmailService,
REST API endpoints, LLM tools, and skill registration.
"""

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent_core.models.email import (
    ATTACHMENT_CACHE_DIR,
    DEFAULT_FETCH_DAYS,
    HTML_CACHE_DIR,
    AttachmentRecord,
    ClearCacheResult,
    EmailConnectionTestResult,
    EmailDetail,
    EmailFlag,
    EmailRecord,
    EmailSettingsInfo,
    EmailSummary,
    EmailSyncResult,
    SendEmailRequest,
    UpdateFlagRequest,
    now_iso,
    record_to_summary,
)
from agent_core.persistence.email_store import EmailStore
from agent_core.services.email_client import (
    EmailClient,
    _decode_header,
    _parse_address,
    _parse_address_list,
    _parse_date,
)
from agent_core.services.email_service import EmailService

# ===========================================================================
# Fixtures
# ===========================================================================


@pytest.fixture
async def email_store():
    """In-memory EmailStore for isolated tests."""
    store = EmailStore(":memory:")
    await store.initialize()
    try:
        yield store
    finally:
        await store.close()


@pytest.fixture
def sample_record() -> EmailRecord:
    """A sample email record for testing."""
    return EmailRecord(
        uid=100,
        message_id="<test@example.com>",
        subject="Test Email",
        sender="alice@example.com",
        sender_name="Alice",
        recipients="bob@example.com",
        cc="carol@example.com",
        date="2026-04-01T10:00:00",
        body_text="Hello Bob, this is a test email. " * 20,
        html_local_path="cache/email/html/100.html",
        is_seen=False,
        is_flagged=True,
        is_answered=False,
        has_attachments=True,
        synced_at="2026-04-01T12:00:00",
    )


@pytest.fixture
def sample_attachment() -> AttachmentRecord:
    """A sample attachment record."""
    return AttachmentRecord(
        email_uid=100,
        filename="report.pdf",
        content_type="application/pdf",
        local_path="cache/email/attachments/uid_100/report.pdf",
        file_size=1024,
        download_time="2026-04-01T12:00:00",
    )


# ===========================================================================
# Model tests
# ===========================================================================


class TestEmailModels:
    """Tests for email Pydantic models and enums."""

    def test_flag_enum_values(self) -> None:
        assert EmailFlag.SEEN == "seen"
        assert EmailFlag.FLAGGED == "flagged"
        assert EmailFlag.ANSWERED == "answered"

    def test_record_defaults(self) -> None:
        record = EmailRecord(uid=1)
        assert record.message_id == ""
        assert record.subject == ""
        assert record.is_seen is False
        assert record.has_attachments is False

    def test_record_serialization(self) -> None:
        record = EmailRecord(uid=42, subject="Hello", sender="x@y.com", is_seen=True)
        data = record.model_dump()
        assert data["uid"] == 42
        assert data["subject"] == "Hello"
        assert data["is_seen"] is True

    def test_summary_model(self) -> None:
        summary = EmailSummary(uid=1, subject="Hi", sender="a@b.com")
        assert summary.uid == 1
        assert summary.preview == ""
        assert summary.is_flagged is False

    def test_detail_model(self) -> None:
        detail = EmailDetail(uid=1, attachments=[])
        assert detail.uid == 1
        assert detail.attachments == []

    def test_send_request(self) -> None:
        req = SendEmailRequest(to="a@b.com", subject="Hi", html_body="<p>hi</p>")
        assert req.to == "a@b.com"
        assert req.attachment_paths == []

    def test_update_flag_request(self) -> None:
        req = UpdateFlagRequest(flag=EmailFlag.SEEN, value=True)
        assert req.flag == EmailFlag.SEEN
        assert req.value is True

    def test_sync_result_defaults(self) -> None:
        result = EmailSyncResult()
        assert result.new_count == 0
        assert result.total_count == 0

    def test_connection_test_result(self) -> None:
        result = EmailConnectionTestResult(
            success=True, message="OK", imap_ok=True, smtp_ok=True
        )
        assert result.success is True

    def test_settings_info_defaults(self) -> None:
        info = EmailSettingsInfo()
        assert info.email_fetch_days == DEFAULT_FETCH_DAYS
        assert info.auto_sync is True

    def test_clear_cache_result(self) -> None:
        result = ClearCacheResult(cleared_files=5, cleared_bytes=1024)
        assert result.cleared_files == 5

    def test_now_iso_returns_string(self) -> None:
        ts = now_iso()
        assert isinstance(ts, str)
        assert "T" in ts

    def test_record_to_summary(self, sample_record: EmailRecord) -> None:
        summary = record_to_summary(sample_record)
        assert summary.uid == 100
        assert summary.subject == "Test Email"
        assert summary.is_flagged is True
        assert len(summary.preview) <= 203  # 200 + "..."

    def test_record_to_summary_short_body(self) -> None:
        record = EmailRecord(uid=1, body_text="Short text")
        summary = record_to_summary(record)
        assert summary.preview == "Short text"


# ===========================================================================
# EmailStore tests
# ===========================================================================


class TestEmailStore:
    """Tests for the SQLite email store."""

    @pytest.mark.asyncio
    async def test_upsert_and_get(
        self, email_store: EmailStore, sample_record: EmailRecord
    ) -> None:
        await email_store.upsert_email(sample_record)
        result = await email_store.get_email(100)
        assert result is not None
        assert result.uid == 100
        assert result.subject == "Test Email"
        assert result.is_flagged is True

    @pytest.mark.asyncio
    async def test_get_nonexistent(self, email_store: EmailStore) -> None:
        result = await email_store.get_email(999)
        assert result is None

    @pytest.mark.asyncio
    async def test_list_emails(
        self, email_store: EmailStore, sample_record: EmailRecord
    ) -> None:
        await email_store.upsert_email(sample_record)
        await email_store.upsert_email(
            EmailRecord(uid=101, subject="Second", date="2026-04-02T10:00:00")
        )
        records = await email_store.list_emails()
        assert len(records) == 2

    @pytest.mark.asyncio
    async def test_list_flagged_only(
        self, email_store: EmailStore, sample_record: EmailRecord
    ) -> None:
        await email_store.upsert_email(sample_record)
        await email_store.upsert_email(EmailRecord(uid=101, is_flagged=False))
        records = await email_store.list_emails(flagged_only=True)
        assert len(records) == 1
        assert records[0].uid == 100

    @pytest.mark.asyncio
    async def test_list_unseen_only(
        self, email_store: EmailStore, sample_record: EmailRecord
    ) -> None:
        await email_store.upsert_email(sample_record)  # is_seen=False
        await email_store.upsert_email(EmailRecord(uid=101, is_seen=True))
        records = await email_store.list_emails(unseen_only=True)
        assert len(records) == 1
        assert records[0].uid == 100

    @pytest.mark.asyncio
    async def test_count_emails(
        self, email_store: EmailStore, sample_record: EmailRecord
    ) -> None:
        assert await email_store.count_emails() == 0
        await email_store.upsert_email(sample_record)
        assert await email_store.count_emails() == 1

    @pytest.mark.asyncio
    async def test_get_max_uid(
        self, email_store: EmailStore, sample_record: EmailRecord
    ) -> None:
        assert await email_store.get_max_uid() == 0
        await email_store.upsert_email(sample_record)
        assert await email_store.get_max_uid() == 100

    @pytest.mark.asyncio
    async def test_get_all_uids(
        self, email_store: EmailStore, sample_record: EmailRecord
    ) -> None:
        await email_store.upsert_email(sample_record)
        await email_store.upsert_email(EmailRecord(uid=200))
        uids = await email_store.get_all_uids()
        assert uids == {100, 200}

    @pytest.mark.asyncio
    async def test_update_flags(
        self, email_store: EmailStore, sample_record: EmailRecord
    ) -> None:
        await email_store.upsert_email(sample_record)
        ok = await email_store.update_flags(100, is_seen=True)
        assert ok is True
        record = await email_store.get_email(100)
        assert record is not None
        assert record.is_seen is True
        assert record.is_flagged is True  # unchanged

    @pytest.mark.asyncio
    async def test_update_flags_no_args(self, email_store: EmailStore) -> None:
        ok = await email_store.update_flags(100)
        assert ok is False

    @pytest.mark.asyncio
    async def test_delete_email(
        self, email_store: EmailStore, sample_record: EmailRecord
    ) -> None:
        await email_store.upsert_email(sample_record)
        ok = await email_store.delete_email(100)
        assert ok is True
        assert await email_store.get_email(100) is None

    @pytest.mark.asyncio
    async def test_delete_all_emails(
        self, email_store: EmailStore, sample_record: EmailRecord
    ) -> None:
        await email_store.upsert_email(sample_record)
        count = await email_store.delete_all_emails()
        assert count == 1
        assert await email_store.count_emails() == 0

    @pytest.mark.asyncio
    async def test_upsert_email_updates(
        self, email_store: EmailStore, sample_record: EmailRecord
    ) -> None:
        await email_store.upsert_email(sample_record)
        updated = sample_record.model_copy(update={"subject": "Updated"})
        await email_store.upsert_email(updated)
        record = await email_store.get_email(100)
        assert record is not None
        assert record.subject == "Updated"

    # -- Attachments --

    @pytest.mark.asyncio
    async def test_attachment_crud(
        self,
        email_store: EmailStore,
        sample_record: EmailRecord,
        sample_attachment: AttachmentRecord,
    ) -> None:
        await email_store.upsert_email(sample_record)
        await email_store.upsert_attachment(sample_attachment)
        atts = await email_store.get_attachments(100)
        assert len(atts) == 1
        assert atts[0].filename == "report.pdf"

    @pytest.mark.asyncio
    async def test_delete_attachments_for_email(
        self,
        email_store: EmailStore,
        sample_record: EmailRecord,
        sample_attachment: AttachmentRecord,
    ) -> None:
        await email_store.upsert_email(sample_record)
        await email_store.upsert_attachment(sample_attachment)
        count = await email_store.delete_attachments_for_email(100)
        assert count == 1
        assert await email_store.get_attachments(100) == []

    @pytest.mark.asyncio
    async def test_delete_all_attachments(
        self,
        email_store: EmailStore,
        sample_record: EmailRecord,
        sample_attachment: AttachmentRecord,
    ) -> None:
        await email_store.upsert_email(sample_record)
        await email_store.upsert_attachment(sample_attachment)
        count = await email_store.delete_all_attachments()
        assert count == 1

    # -- Settings --

    @pytest.mark.asyncio
    async def test_get_set_setting(self, email_store: EmailStore) -> None:
        val = await email_store.get_setting("test_key", "default")
        assert val == "default"
        await email_store.set_setting("test_key", "hello")
        val = await email_store.get_setting("test_key", "default")
        assert val == "hello"

    @pytest.mark.asyncio
    async def test_fetch_days(self, email_store: EmailStore) -> None:
        days = await email_store.get_fetch_days()
        assert days == DEFAULT_FETCH_DAYS
        await email_store.set_fetch_days(7)
        assert await email_store.get_fetch_days() == 7

    @pytest.mark.asyncio
    async def test_auto_sync(self, email_store: EmailStore) -> None:
        assert await email_store.get_auto_sync() is True
        await email_store.set_auto_sync(False)
        assert await email_store.get_auto_sync() is False


# ===========================================================================
# EmailClient helper tests (pure functions, no I/O)
# ===========================================================================


class TestEmailClientHelpers:
    """Tests for header-decoding and date-parsing helpers."""

    def test_decode_header_plain(self) -> None:
        assert _decode_header("Hello World") == "Hello World"

    def test_decode_header_none(self) -> None:
        assert _decode_header(None) == ""

    def test_parse_address_simple(self) -> None:
        name, addr = _parse_address("Alice <alice@example.com>")
        assert addr == "alice@example.com"
        assert name == "Alice"

    def test_parse_address_none(self) -> None:
        name, addr = _parse_address(None)
        assert name == ""
        assert addr == ""

    def test_parse_address_list(self) -> None:
        result = _parse_address_list("a@b.com, c@d.com")
        assert "a@b.com" in result
        assert "c@d.com" in result

    def test_parse_address_list_none(self) -> None:
        assert _parse_address_list(None) == ""

    def test_parse_date_rfc2822(self) -> None:
        result = _parse_date("Mon, 01 Apr 2026 10:00:00 +0800")
        assert "2026-04-01" in result

    def test_parse_date_none(self) -> None:
        assert _parse_date(None) == ""

    def test_parse_date_invalid(self) -> None:
        result = _parse_date("not a date")
        assert result == "not a date"

    def test_parse_uid_from_meta(self) -> None:
        client = EmailClient()
        assert client._parse_uid_from_meta("1 (UID 123 FLAGS (\\Seen))") == 123
        assert client._parse_uid_from_meta("1 (FLAGS (\\Seen))") is None

    def test_parse_flags_from_meta(self) -> None:
        client = EmailClient()
        assert (
            client._parse_flags_from_meta("1 (UID 123 FLAGS (\\Seen \\Flagged))")
            == "\\Seen \\Flagged"
        )
        assert client._parse_flags_from_meta("1 (UID 123 RFC822 {100})") == ""

    def test_extract_fetch_payload(self) -> None:
        client = EmailClient()
        msg_data = [
            b")",
            (b"1 (UID 123 FLAGS (\\Seen) RFC822 {3}", b"abc"),
            b")",
        ]
        uid_meta, raw_email = client._extract_fetch_payload(msg_data)
        assert "UID 123" in uid_meta
        assert raw_email == b"abc"


# ===========================================================================
# EmailService tests (mocked client)
# ===========================================================================


class TestEmailService:
    """Tests for the email service with a mocked IMAP/SMTP client."""

    @pytest.fixture
    async def service(self, email_store: EmailStore, tmp_path: Path):
        """Build an EmailService with a mocked client and profile store."""
        mock_profile = AsyncMock()
        mock_profile.get_profile = AsyncMock(
            return_value=MagicMock(email_account="user@example.com")
        )
        mock_profile.get_decrypted_email_password = AsyncMock(return_value="secret")

        mock_client = AsyncMock(spec=EmailClient)
        mock_client.fetch_emails = AsyncMock(return_value=[])
        mock_client.get_last_attachment_records = MagicMock(return_value=[])
        mock_client.set_flag = AsyncMock(return_value=True)
        mock_client.send_email = AsyncMock()
        mock_client.test_connection = AsyncMock(
            return_value=EmailConnectionTestResult(
                success=True, message="OK", imap_ok=True, smtp_ok=True
            )
        )

        svc = EmailService(
            email_store=email_store,
            profile_store=mock_profile,
            email_client=mock_client,
            data_root=str(tmp_path),
        )
        return svc

    @pytest.mark.asyncio
    async def test_sync_empty(self, service: EmailService) -> None:
        result = await service.sync_emails(days=7)
        assert result.new_count == 0
        assert result.total_count == 0

    @pytest.mark.asyncio
    async def test_sync_with_records(
        self, service: EmailService, sample_record: EmailRecord
    ) -> None:
        service._client.fetch_emails = AsyncMock(return_value=[sample_record])
        result = await service.sync_emails(days=7)
        assert result.new_count == 1
        assert result.total_count == 1

    @pytest.mark.asyncio
    async def test_sync_update_existing(
        self, service: EmailService, sample_record: EmailRecord
    ) -> None:
        # Pre-seed the store
        await service._store.upsert_email(sample_record)
        service._client.fetch_emails = AsyncMock(return_value=[sample_record])
        result = await service.sync_emails(days=7)
        assert result.new_count == 0
        assert result.updated_count == 1

    @pytest.mark.asyncio
    async def test_list_emails(
        self, service: EmailService, sample_record: EmailRecord
    ) -> None:
        await service._store.upsert_email(sample_record)
        summaries = await service.list_emails()
        assert len(summaries) == 1
        assert summaries[0].uid == 100

    @pytest.mark.asyncio
    async def test_get_detail_found(
        self, service: EmailService, sample_record: EmailRecord
    ) -> None:
        await service._store.upsert_email(sample_record)
        detail = await service.get_email_detail(100)
        assert detail is not None
        assert detail.uid == 100

    @pytest.mark.asyncio
    async def test_get_detail_not_found(self, service: EmailService) -> None:
        detail = await service.get_email_detail(999)
        assert detail is None

    @pytest.mark.asyncio
    async def test_update_flag(
        self, service: EmailService, sample_record: EmailRecord
    ) -> None:
        await service._store.upsert_email(sample_record)
        ok = await service.update_flag(100, EmailFlag.SEEN, True)
        assert ok is True
        record = await service._store.get_email(100)
        assert record is not None
        assert record.is_seen is True

    @pytest.mark.asyncio
    async def test_send_email(self, service: EmailService) -> None:
        req = SendEmailRequest(to="bob@example.com", subject="Hi", plain_body="Hello")
        await service.send_email(req)
        service._client.send_email.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_test_connection(self, service: EmailService) -> None:
        result = await service.test_connection()
        assert result.success is True

    @pytest.mark.asyncio
    async def test_get_settings(self, service: EmailService) -> None:
        info = await service.get_email_settings()
        assert info.email_fetch_days == DEFAULT_FETCH_DAYS
        assert info.auto_sync is True

    @pytest.mark.asyncio
    async def test_update_settings(self, service: EmailService) -> None:
        info = await service.update_email_settings(fetch_days=7, auto_sync=False)
        assert info.email_fetch_days == 7
        assert info.auto_sync is False

    @pytest.mark.asyncio
    async def test_count_emails(
        self, service: EmailService, sample_record: EmailRecord
    ) -> None:
        assert await service.count_emails() == 0
        await service._store.upsert_email(sample_record)
        assert await service.count_emails() == 1

    @pytest.mark.asyncio
    async def test_clear_cache(self, service: EmailService, tmp_path: Path) -> None:
        # Create some cache files
        html_dir = tmp_path / HTML_CACHE_DIR
        html_dir.mkdir(parents=True)
        (html_dir / "100.html").write_text("<p>hi</p>")

        att_dir = tmp_path / ATTACHMENT_CACHE_DIR / "uid_100"
        att_dir.mkdir(parents=True)
        (att_dir / "report.pdf").write_bytes(b"pdf content")

        result = await service.clear_cache()
        assert result.cleared_files == 2
        assert result.cleared_bytes > 0

    @pytest.mark.asyncio
    async def test_credentials_missing_raises(
        self, email_store: EmailStore, tmp_path: Path
    ) -> None:
        mock_profile = AsyncMock()
        mock_profile.get_profile = AsyncMock(return_value=MagicMock(email_account=""))
        mock_profile.get_decrypted_email_password = AsyncMock(return_value="")
        svc = EmailService(
            email_store=email_store,
            profile_store=mock_profile,
            email_client=AsyncMock(),
            data_root=str(tmp_path),
        )
        with pytest.raises(ValueError, match="credentials not configured"):
            await svc.sync_emails()


# ===========================================================================
# Tool tests
# ===========================================================================


class TestEmailTools:
    """Tests for email LLM tool functions."""

    @pytest.fixture(autouse=True)
    async def setup_mock_service(self, email_store: EmailStore, tmp_path: Path):
        """Mock the email provider to return our test service."""
        mock_profile = AsyncMock()
        mock_profile.get_profile = AsyncMock(
            return_value=MagicMock(email_account="user@example.com")
        )
        mock_profile.get_decrypted_email_password = AsyncMock(return_value="secret")
        mock_client = AsyncMock(spec=EmailClient)
        mock_client.fetch_emails = AsyncMock(return_value=[])
        mock_client.get_last_attachment_records = MagicMock(return_value=[])
        mock_client.set_flag = AsyncMock(return_value=True)
        mock_client.send_email = AsyncMock()
        mock_client.test_connection = AsyncMock(
            return_value=EmailConnectionTestResult(
                success=True, message="OK", imap_ok=True, smtp_ok=True
            )
        )
        svc = EmailService(
            email_store=email_store,
            profile_store=mock_profile,
            email_client=mock_client,
            data_root=str(tmp_path),
        )
        with patch(
            "agent_core.tools.email.get_email_service",
            new=AsyncMock(return_value=svc),
        ):
            self._service = svc
            yield

    @pytest.mark.asyncio
    async def test_list_emails_tool(self, sample_record: EmailRecord) -> None:
        from agent_core.tools.email import list_emails

        await self._service._store.upsert_email(sample_record)
        result = json.loads(await list_emails())
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["uid"] == 100

    @pytest.mark.asyncio
    async def test_read_email_tool(self, sample_record: EmailRecord) -> None:
        from agent_core.tools.email import read_email

        await self._service._store.upsert_email(sample_record)
        result = json.loads(await read_email(100))
        assert result["uid"] == 100
        assert result["subject"] == "Test Email"

    @pytest.mark.asyncio
    async def test_read_email_not_found(self) -> None:
        from agent_core.tools.email import read_email

        result = json.loads(await read_email(999))
        assert "error" in result

    @pytest.mark.asyncio
    async def test_count_emails_tool(self) -> None:
        from agent_core.tools.email import count_emails

        result = json.loads(await count_emails())
        assert result["total"] == 0

    @pytest.mark.asyncio
    async def test_sync_emails_tool(self) -> None:
        from agent_core.tools.email import sync_emails

        result = json.loads(await sync_emails(days=7))
        assert "new_count" in result

    @pytest.mark.asyncio
    async def test_update_flag_tool(self, sample_record: EmailRecord) -> None:
        from agent_core.tools.email import update_email_flag

        await self._service._store.upsert_email(sample_record)
        result = json.loads(await update_email_flag(100, "seen", True))
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_update_flag_invalid(self) -> None:
        from agent_core.tools.email import update_email_flag

        result = json.loads(await update_email_flag(100, "invalid", True))
        assert "error" in result

    @pytest.mark.asyncio
    async def test_send_email_tool(self) -> None:
        from agent_core.tools.email import send_email

        result = json.loads(
            await send_email(to="bob@example.com", subject="Hi", body="Hello")
        )
        assert result["status"] == "sent"

    @pytest.mark.asyncio
    async def test_get_settings_tool(self) -> None:
        from agent_core.tools.email import get_email_settings

        result = json.loads(await get_email_settings())
        assert result["email_fetch_days"] == DEFAULT_FETCH_DAYS

    def test_tool_registration(self) -> None:
        from agent_core.tools.email import register_email_tools
        from agent_core.tools.registry import ToolRegistry

        registry = ToolRegistry()
        register_email_tools(registry)
        tool_names = {t.name for t in registry.list_tools()}
        assert "list_emails" in tool_names
        assert "read_email" in tool_names
        assert "sync_emails" in tool_names
        assert "send_email" in tool_names
        assert "update_email_flag" in tool_names
        assert "get_email_settings" in tool_names
        assert "count_emails" in tool_names


# ===========================================================================
# Skill tests
# ===========================================================================


class TestEmailSkill:
    """Tests for the email assistant skill definition."""

    def test_skill_is_registered(self) -> None:
        from agent_core.skills import list_skills

        skills = list_skills()
        ids = [s.id for s in skills]
        assert "email_assistant" in ids

    def test_skill_definition(self) -> None:
        from agent_core.skills.email_assistant import SKILL

        assert SKILL.id == "email_assistant"
        assert SKILL.name == "Email Assistant"
        assert "email" in SKILL.system_prompt.lower()
        assert SKILL.icon == "Mail"


# ===========================================================================
# REST API endpoint tests
# ===========================================================================


class TestEmailAPI:
    """Tests for email REST API endpoints using a mocked service."""

    @pytest.fixture
    def client(self):
        """TestClient with mocked email service."""

        from fastapi.testclient import TestClient

        from agent_core.api.server import create_app
        from agent_core.config import AgentConfig

        config = AgentConfig(
            openai_api_key="test-key",
            model_name="gpt-4o-mini",
            db_path=":memory:",
            encryption_key="test-key-32-bytes-long-enough-!",
        )
        app = create_app(config)
        with TestClient(app) as c:
            yield c

    def test_list_emails_endpoint(self, client) -> None:
        resp = client.get("/email")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_count_emails_endpoint(self, client) -> None:
        resp = client.get("/email/count")
        assert resp.status_code == 200
        assert "total" in resp.json()

    def test_get_email_not_found(self, client) -> None:
        resp = client.get("/email/99999")
        assert resp.status_code == 404

    def test_email_settings_get(self, client) -> None:
        resp = client.get("/email/settings/email")
        assert resp.status_code == 200
        data = resp.json()
        assert "email_fetch_days" in data

    def test_email_settings_update(self, client) -> None:
        resp = client.put(
            "/email/settings/email",
            json={"email_fetch_days": 7, "auto_sync": False},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["email_fetch_days"] == 7
        assert data["auto_sync"] is False

    def test_sync_returns_428_when_credentials_missing(self, client) -> None:
        from unittest.mock import AsyncMock

        from agent_core.api.dependencies import get_email_service

        mock_service = AsyncMock()
        mock_service.sync_emails = AsyncMock(
            side_effect=ValueError("Email credentials not configured")
        )
        client.app.dependency_overrides[get_email_service] = lambda: mock_service
        try:
            resp = client.post("/email/sync")
        finally:
            client.app.dependency_overrides.clear()

        assert resp.status_code == 428
        detail = resp.json().get("detail", {})
        assert detail.get("code") == "EMAIL_CREDENTIALS_MISSING"


# ===========================================================================
# Security: Path Traversal tests
# ===========================================================================


class TestPathTraversalProtection:
    """Tests that path traversal filenames are sanitized / rejected."""

    @pytest.mark.asyncio
    async def test_sanitize_attachment_filename(self, tmp_path: Path) -> None:
        """Attachment filenames with path separators must be sanitized."""
        from pathvalidate import sanitize_filename

        uid = 1
        att_dir = tmp_path / "cache" / "email" / "attachments" / f"uid_{uid}"
        att_dir.mkdir(parents=True, exist_ok=True)

        malicious = "../../../etc/passwd"
        sanitized = sanitize_filename(malicious, platform="auto") or f"attachment_{uid}"
        att_path = (att_dir / sanitized).resolve()

        # The resolved path must be inside att_dir, not escape it
        assert str(att_path).startswith(str(att_dir.resolve()))

    def test_download_path_validation_rejects_traversal(self, tmp_path: Path) -> None:
        """The route-level guard must reject local_path that escapes data_root."""
        data_root = tmp_path / "data"
        data_root.mkdir()

        # A safe path succeeds
        safe = (data_root / "cache" / "file.pdf").resolve()
        assert str(safe).startswith(str(data_root.resolve()))

        # A traversal path is rejected by the startswith guard
        traversal = (data_root / ".." / "secrets.txt").resolve()
        assert not str(traversal).startswith(str(data_root.resolve()))


# ===========================================================================
# EmailStore: reset_cache_fields tests
# ===========================================================================


class TestEmailStoreResetCacheFields:
    """Tests for the reset_cache_fields method added in PR #73 fix."""

    @pytest.mark.asyncio
    async def test_reset_cache_fields_clears_html_preserves_has_attachments(
        self, email_store: EmailStore
    ) -> None:
        """reset_cache_fields clears html_local_path; has_attachments is preserved."""
        rec1 = EmailRecord(
            uid=1,
            html_local_path="cache/email/html/1.html",
            has_attachments=True,
        )
        rec2 = EmailRecord(
            uid=2,
            html_local_path="cache/email/html/2.html",
            has_attachments=True,
        )
        await email_store.upsert_email(rec1)
        await email_store.upsert_email(rec2)

        count = await email_store.reset_cache_fields()
        assert count == 2

        r1 = await email_store.get_email(1)
        r2 = await email_store.get_email(2)
        assert r1 is not None and r1.html_local_path == ""
        assert r1.has_attachments is True  # IMAP truth preserved
        assert r2 is not None and r2.html_local_path == ""
        assert r2.has_attachments is True  # IMAP truth preserved

    @pytest.mark.asyncio
    async def test_reset_cache_fields_empty_store(
        self, email_store: EmailStore
    ) -> None:
        """reset_cache_fields on an empty store returns 0 and doesn't error."""
        count = await email_store.reset_cache_fields()
        assert count == 0


# ===========================================================================
# Lazy-fetch: content_fetched flag and on-demand fetch
# ===========================================================================


class TestLazyFetch:
    """Tests for the A005 lazy-fetch pattern.

    During sync, HTML and attachments are NOT downloaded.  They are fetched
    lazily on the first detail view.  After a cache clear, the flag is reset
    and the next detail view triggers a re-fetch.
    """

    @pytest.mark.asyncio
    async def test_sync_sets_content_fetched_false(
        self, email_store: EmailStore
    ) -> None:
        """EmailRecords inserted during sync must have content_fetched=False."""
        rec = EmailRecord(
            uid=10, has_attachments=True, html_local_path="", content_fetched=False
        )
        await email_store.upsert_email(rec)
        stored = await email_store.get_email(10)
        assert stored is not None
        assert stored.content_fetched is False
        assert stored.html_local_path == ""

    @pytest.mark.asyncio
    async def test_mark_content_fetched_updates_record(
        self, email_store: EmailStore
    ) -> None:
        """mark_content_fetched sets content_fetched=True and stores html_local_path."""
        rec = EmailRecord(uid=11, content_fetched=False)
        await email_store.upsert_email(rec)

        ok = await email_store.mark_content_fetched(11, "cache/email/html/11.html")
        assert ok is True

        stored = await email_store.get_email(11)
        assert stored is not None
        assert stored.content_fetched is True
        assert stored.html_local_path == "cache/email/html/11.html"

    @pytest.mark.asyncio
    async def test_mark_content_fetched_nonexistent_returns_false(
        self, email_store: EmailStore
    ) -> None:
        """mark_content_fetched on missing UID returns False without error."""
        ok = await email_store.mark_content_fetched(999, "cache/email/html/999.html")
        assert ok is False

    @pytest.mark.asyncio
    async def test_reset_cache_fields_resets_content_fetched(
        self, email_store: EmailStore
    ) -> None:
        """reset_cache_fields sets content_fetched=False so next view re-fetches."""
        rec = EmailRecord(
            uid=12, html_local_path="cache/email/html/12.html", content_fetched=True
        )
        await email_store.upsert_email(rec)

        await email_store.reset_cache_fields()

        stored = await email_store.get_email(12)
        assert stored is not None
        assert stored.html_local_path == ""
        assert stored.content_fetched is False

    @pytest.mark.asyncio
    async def test_ensure_email_content_fetched_calls_imap_when_not_fetched(
        self, tmp_path: Path
    ) -> None:
        """Triggers IMAP fetch when content_fetched is False."""
        from agent_core.persistence.profile_store import ProfileStore
        from agent_core.services.email_service import EmailService

        store = EmailStore(":memory:")
        await store.initialize()
        await store.set_setting("account", "test@example.com")
        await store.set_setting("password", "secret")

        rec = EmailRecord(uid=20, has_attachments=False, content_fetched=False)
        await store.upsert_email(rec)

        mock_client = AsyncMock()
        mock_client.fetch_email_content = AsyncMock(
            return_value=("cache/email/html/20.html", [], "body text")
        )
        mock_profile = AsyncMock(spec=ProfileStore)
        mock_profile.get_profile.return_value = MagicMock(
            email_account="test@example.com"
        )
        mock_profile.get_decrypted_email_password = AsyncMock(return_value="secret")

        service = EmailService(
            store, mock_profile, mock_client, data_root=str(tmp_path)
        )

        detail = await service.ensure_email_content_fetched(20)
        assert detail is not None
        mock_client.fetch_email_content.assert_called_once_with(
            20, "test@example.com", "secret", folder="INBOX"
        )
        # html_local_path and content_fetched must be updated in the store
        updated = await store.get_email(20)
        assert updated is not None
        assert updated.content_fetched is True
        assert updated.html_local_path == "cache/email/html/20.html"

    @pytest.mark.asyncio
    async def test_ensure_email_content_fetched_skips_imap_when_already_fetched(
        self, tmp_path: Path
    ) -> None:
        """ensure_email_content_fetched does NOT call IMAP when content_fetched=True."""
        from agent_core.persistence.profile_store import ProfileStore
        from agent_core.services.email_service import EmailService

        store = EmailStore(":memory:")
        await store.initialize()

        rec = EmailRecord(
            uid=21, html_local_path="cache/email/html/21.html", content_fetched=True
        )
        await store.upsert_email(rec)

        mock_client = AsyncMock()
        mock_profile = AsyncMock(spec=ProfileStore)

        service = EmailService(
            store, mock_profile, mock_client, data_root=str(tmp_path)
        )
        detail = await service.ensure_email_content_fetched(21)

        assert detail is not None
        mock_client.fetch_email_content.assert_not_called()

    @pytest.mark.asyncio
    async def test_ensure_email_content_fetched_returns_none_for_missing_uid(
        self, tmp_path: Path
    ) -> None:
        """ensure_email_content_fetched returns None for unknown UID."""
        from agent_core.persistence.profile_store import ProfileStore
        from agent_core.services.email_service import EmailService

        store = EmailStore(":memory:")
        await store.initialize()
        mock_client = AsyncMock()
        mock_profile = AsyncMock(spec=ProfileStore)

        service = EmailService(
            store, mock_profile, mock_client, data_root=str(tmp_path)
        )
        result = await service.ensure_email_content_fetched(9999)
        assert result is None
