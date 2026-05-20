"""Tests for the policy search module — ingest, index, retriever, tool, skill."""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from agent_core.models.skills import SkillType
from agent_core.policy_search.ingest import (
    _detect_section_heading,
    _extract_title_from_filename,
    _generate_doc_id,
    chunk_text,
    ingest_pdf,
)
from agent_core.policy_search.models import ChunkMetadata, RetrievalResult, TextChunk
from agent_core.skills import get_skill
from agent_core.tools import auto_discover_and_register
from agent_core.tools.registry import ToolRegistry

# ---------------------------------------------------------------------------
# Model tests
# ---------------------------------------------------------------------------


class TestPolicySearchConfig:
    """Tests for policy search configuration."""

    def test_config_defaults(self) -> None:
        from agent_core.policy_search.config import (
            DEFAULT_CHUNK_OVERLAP,
            DEFAULT_CHUNK_SIZE,
            DEFAULT_INDEX_DIR,
            DEFAULT_PDF_DIR,
            PolicySearchConfig,
        )

        config = PolicySearchConfig()
        assert config.pdf_dir == DEFAULT_PDF_DIR
        assert config.index_dir == DEFAULT_INDEX_DIR
        assert config.chunk_size == DEFAULT_CHUNK_SIZE
        assert config.chunk_overlap == DEFAULT_CHUNK_OVERLAP

    @patch.dict(
        "os.environ",
        {
            "POLICY_PDF_DIR": "custom-pdfs",
            "POLICY_INDEX_DIR": "custom-index",
            "POLICY_CHUNK_SIZE": "700",
            "POLICY_CHUNK_OVERLAP": "90",
        },
    )
    def test_config_from_env(self) -> None:
        from agent_core.policy_search.config import DEFAULT_PDF_DIR, PolicySearchConfig

        config = PolicySearchConfig.from_env()
        assert config.pdf_dir == DEFAULT_PDF_DIR.parent / "custom-pdfs"
        assert config.index_dir == DEFAULT_PDF_DIR.parent / "custom-index"
        assert config.chunk_size == 700
        assert config.chunk_overlap == 90

    def test_config_with_overrides(self) -> None:
        from agent_core.policy_search.config import PolicySearchConfig

        base = PolicySearchConfig(chunk_size=500, chunk_overlap=100)
        updated = base.with_overrides(chunk_size=800)
        assert updated.chunk_size == 800
        assert updated.chunk_overlap == 100


class TestModels:
    """Tests for policy search data models."""

    def test_chunk_metadata_creation(self) -> None:
        meta = ChunkMetadata(doc_id="abc123", title="Test", page=3, section="Ch1")
        assert meta.doc_id == "abc123"
        assert meta.page == 3

    def test_text_chunk_creation(self) -> None:
        meta = ChunkMetadata(doc_id="x", title="T", page=1)
        chunk = TextChunk(chunk_id="x_0001", text="Some content", metadata=meta)
        assert chunk.chunk_id == "x_0001"
        assert chunk.text == "Some content"

    def test_text_chunk_serialization_roundtrip(self) -> None:
        meta = ChunkMetadata(doc_id="abc", title="Title", page=5, section="Sec")
        chunk = TextChunk(chunk_id="abc_0000", text="Hello", metadata=meta)
        json_str = chunk.model_dump_json()
        restored = TextChunk(**json.loads(json_str))
        assert restored.chunk_id == chunk.chunk_id
        assert restored.metadata.page == 5

    def test_retrieval_result(self) -> None:
        result = RetrievalResult(
            snippet="content",
            score=0.5,
            title="Doc",
            page=2,
            section="Sec",
            chunk_id="id_0001",
        )
        assert result.score == 0.5
        assert result.title == "Doc"


# ---------------------------------------------------------------------------
# Ingest tests
# ---------------------------------------------------------------------------


class TestIngest:
    """Tests for PDF ingestion and chunking."""

    def test_generate_doc_id_stable(self) -> None:
        path = Path("/some/dir/test.pdf")
        id1 = _generate_doc_id(path)
        id2 = _generate_doc_id(path)
        assert id1 == id2
        assert len(id1) == 12

    def test_generate_doc_id_different_files(self) -> None:
        p1 = Path("a.pdf")
        p2 = Path("b.pdf")
        assert _generate_doc_id(p1) != _generate_doc_id(p2)

    def test_extract_title_from_filename(self) -> None:
        assert _extract_title_from_filename(Path("plain.pdf")) == "plain"

    def test_detect_section_heading_chinese(self) -> None:  # nosemgrep
        assert _detect_section_heading("普通文本内容\n更多内容") == ""  # nosemgrep
        assert _detect_section_heading("1. Item\nContent") == "1. Item"

    def test_chunk_text_basic(self) -> None:
        pages = [{"text": "A" * 600, "page": 1}, {"text": "B" * 400, "page": 2}]
        chunks = chunk_text(pages, chunk_size=500, chunk_overlap=100)
        assert len(chunks) >= 2
        for c in chunks:
            assert len(str(c["text"])) <= 500 or c == chunks[-1]

    def test_chunk_text_preserves_page(self) -> None:
        pages = [{"text": "X" * 200, "page": 3}]
        chunks = chunk_text(pages, chunk_size=500, chunk_overlap=50)
        assert len(chunks) == 1
        assert chunks[0]["page"] == 3

    def test_chunk_text_empty_input(self) -> None:
        chunks = chunk_text([], chunk_size=500, chunk_overlap=100)
        assert chunks == []

    def test_ingest_pdf_with_real_file(self) -> None:
        """Test ingestion with an actual PDF from the pdfs/ directory."""
        pdf_dir = Path(__file__).resolve().parents[2] / "pdfs"
        if not pdf_dir.exists():
            pdf_dir = Path(__file__).resolve().parents[3] / "pdfs"
        pdf_files = list(pdf_dir.glob("*.pdf")) if pdf_dir.exists() else []
        if not pdf_files:
            pytest.skip("No PDF files available for testing")
        chunks = ingest_pdf(pdf_files[0], chunk_size=500, chunk_overlap=100)
        assert len(chunks) > 0
        for chunk in chunks:
            assert chunk.chunk_id
            assert chunk.text
            assert chunk.metadata.doc_id
            assert chunk.metadata.title
            assert chunk.metadata.page >= 1


# ---------------------------------------------------------------------------
# Index tests (mocked embeddings)
# ---------------------------------------------------------------------------


class TestIndex:
    """Tests for FAISS index build/save/load (with mocked embeddings)."""

    def _make_chunks(self, n: int = 5) -> list[TextChunk]:
        return [
            TextChunk(
                chunk_id=f"test_{i:04d}",
                text=f"Test chunk content {i}",
                metadata=ChunkMetadata(doc_id="testdoc", title="Test", page=i + 1),
            )
            for i in range(n)
        ]

    @patch("agent_core.policy_search.index.get_embeddings")
    def test_build_index(self, mock_embed: MagicMock) -> None:
        from agent_core.policy_search.index import build_index

        chunks = self._make_chunks(3)
        mock_embed.return_value = np.random.rand(3, 128).tolist()
        index, result_chunks = build_index(chunks)
        assert index.ntotal == 3
        assert len(result_chunks) == 3
        mock_embed.assert_called_once()

    @patch("agent_core.policy_search.index.get_embeddings")
    def test_build_index_empty_raises(self, mock_embed: MagicMock) -> None:
        from agent_core.policy_search.index import build_index

        with pytest.raises(ValueError, match="empty"):
            build_index([])

    @patch("agent_core.policy_search.index.get_embeddings")
    def test_save_and_load_index(self, mock_embed: MagicMock) -> None:
        from agent_core.policy_search.index import build_index, load_index, save_index

        chunks = self._make_chunks(5)
        mock_embed.return_value = np.random.rand(5, 64).tolist()
        index, ordered = build_index(chunks)
        with tempfile.TemporaryDirectory() as tmpdir:
            out_dir = Path(tmpdir)
            save_index(index, ordered, out_dir)
            loaded_index, loaded_chunks = load_index(out_dir)
            assert loaded_index.ntotal == 5
            assert len(loaded_chunks) == 5
            assert loaded_chunks[0].chunk_id == "test_0000"
            assert loaded_chunks[0].metadata.title == "Test"

    def test_load_index_missing_raises(self) -> None:
        from agent_core.policy_search.index import load_index

        with pytest.raises(FileNotFoundError):
            load_index(Path("/nonexistent/path"))

    def test_get_missing_index_files(self) -> None:
        from agent_core.policy_search.index import get_missing_index_files

        with tempfile.TemporaryDirectory() as tmpdir:
            index_dir = Path(tmpdir)
            missing = get_missing_index_files(index_dir)
            assert {path.name for path in missing} == {"faiss.index", "chunks.jsonl"}

            (index_dir / "faiss.index").touch()
            missing = get_missing_index_files(index_dir)
            assert [path.name for path in missing] == ["chunks.jsonl"]

            (index_dir / "chunks.jsonl").touch()
            assert get_missing_index_files(index_dir) == []

    def test_log_index_startup_check_warns_when_missing(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        import logging

        from agent_core.policy_search.index import log_index_startup_check

        with tempfile.TemporaryDirectory() as tmpdir:
            caplog.set_level(logging.WARNING, logger="agent_core.policy_search.index")
            log_index_startup_check(Path(tmpdir))

        assert "Policy search index is missing" in caplog.text
        assert "build-policy-index" in caplog.text

    @patch("agent_core.policy_search.build_index.save_index")
    @patch("agent_core.policy_search.build_index.build_index")
    @patch("agent_core.policy_search.build_index.ingest_directory")
    def test_rebuild_policy_index(
        self,
        mock_ingest: MagicMock,
        mock_build: MagicMock,
        mock_save: MagicMock,
    ) -> None:
        from agent_core.policy_search.build_index import rebuild_policy_index

        chunks = self._make_chunks(2)
        mock_ingest.return_value = chunks
        mock_index = MagicMock()
        mock_index.ntotal = 2
        mock_build.return_value = (mock_index, chunks)

        with tempfile.TemporaryDirectory() as tmpdir:
            pdf_dir = Path(tmpdir) / "pdfs"
            pdf_dir.mkdir()
            output_dir = Path(tmpdir) / "index"
            result = rebuild_policy_index(
                pdf_dir=pdf_dir,
                output_dir=output_dir,
                chunk_size=600,
                chunk_overlap=80,
            )

        mock_ingest.assert_called_once_with(pdf_dir, 600, 80)
        mock_build.assert_called_once_with(chunks)
        mock_save.assert_called_once_with(mock_index, chunks, output_dir)
        assert result.chunk_count == 2
        assert result.vector_count == 2

    def test_rebuild_policy_index_missing_pdf_dir_raises(self) -> None:
        from agent_core.policy_search.build_index import rebuild_policy_index

        with pytest.raises(FileNotFoundError):
            rebuild_policy_index(pdf_dir=Path("/nonexistent/pdfs"))


# ---------------------------------------------------------------------------
# Retriever tests (mocked)
# ---------------------------------------------------------------------------


class TestRetriever:
    """Tests for the retriever search and formatting."""

    @patch("agent_core.policy_search.retriever.load_index")
    @patch("agent_core.policy_search.retriever.get_query_embedding")
    def test_search_returns_results(
        self, mock_embed: MagicMock, mock_load: MagicMock
    ) -> None:
        import faiss

        from agent_core.policy_search.retriever import search, set_index_dir

        dim = 64
        n_chunks = 3
        vectors = np.random.rand(n_chunks, dim).astype(np.float32)
        index = faiss.IndexFlatL2(dim)
        index.add(vectors)
        chunks = [
            TextChunk(
                chunk_id=f"t_{i}",
                text=f"Chunk {i}",
                metadata=ChunkMetadata(doc_id="d", title="Title", page=i + 1),
            )
            for i in range(n_chunks)
        ]
        mock_load.return_value = (index, chunks)
        mock_embed.return_value = np.random.rand(dim).tolist()
        with tempfile.TemporaryDirectory() as tmpdir:
            set_index_dir(Path(tmpdir))
            results = search("test query", top_k=2)
        assert len(results) == 2
        assert all(isinstance(r, RetrievalResult) for r in results)
        assert results[0].title == "Title"


# ---------------------------------------------------------------------------
# Tool registration tests
# ---------------------------------------------------------------------------


class TestToolRegistration:
    """Tests for the policy search tool registration."""

    def test_tool_is_auto_discovered(self) -> None:
        registry = ToolRegistry()
        auto_discover_and_register(registry)
        tool_names = {t.name for t in registry.list_tools()}
        assert "search_campus_policy" in tool_names

    def test_tool_is_safe(self) -> None:
        registry = ToolRegistry()
        auto_discover_and_register(registry)
        assert not registry.is_sensitive("search_campus_policy")

    def test_tool_has_description(self) -> None:
        registry = ToolRegistry()
        auto_discover_and_register(registry)
        tool_def = registry.get("search_campus_policy")
        assert tool_def is not None
        assert "policy" in tool_def.description.lower()
        assert len(tool_def.description) > 20


# ---------------------------------------------------------------------------
# Skill tests
# ---------------------------------------------------------------------------


class TestSkillUpdate:
    """Tests for the updated policy search skill."""

    def test_skill_exists(self) -> None:
        skill = get_skill(SkillType.POLICY_SEARCH)
        assert skill is not None
        assert skill.name == "Policy Search"

    def test_skill_prompt_requires_tool(self) -> None:
        skill = get_skill(SkillType.POLICY_SEARCH)
        assert skill is not None
        assert "search_campus_policy" in skill.system_prompt

    def test_skill_prompt_requires_citations(self) -> None:  # nosemgrep
        skill = get_skill(SkillType.POLICY_SEARCH)
        assert skill is not None
        assert "[来源" in skill.system_prompt  # nosemgrep

    def test_skill_prompt_forbids_fabrication(self) -> None:  # nosemgrep
        skill = get_skill(SkillType.POLICY_SEARCH)
        assert skill is not None
        assert (
            "未找到" in skill.system_prompt  # nosemgrep
            or "不得" in skill.system_prompt  # nosemgrep
        )
