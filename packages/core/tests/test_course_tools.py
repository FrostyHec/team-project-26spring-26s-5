"""Tests for course_tools module."""

import json
import os
import tempfile
from collections.abc import Generator

import pytest


@pytest.fixture
def temp_file() -> Generator[str, None, None]:
    """Create a temporary file and clean it up after the test."""
    with tempfile.NamedTemporaryFile(delete=False) as f:
        temp_path = f.name

    try:
        yield temp_path
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)


@pytest.fixture
def temp_pdf_file() -> Generator[str, None, None]:
    """Create a temporary PDF file and clean it up after the test."""
    from pypdf import PdfWriter

    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        writer.write(f.name)
        temp_path = f.name

    try:
        yield temp_path
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)


@pytest.fixture
def temp_docx_file() -> Generator[str, None, None]:
    """Create a temporary DOCX file and clean it up after the test."""
    from docx import Document

    doc = Document()
    doc.add_paragraph("This is a Word document test.")
    doc.add_paragraph("Second paragraph with more content.")

    with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as f:
        doc.save(f.name)
        temp_path = f.name

    try:
        yield temp_path
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)


@pytest.fixture
def temp_pptx_file() -> Generator[str, None, None]:
    """Create a temporary PPTX file and clean it up after the test."""
    from pptx import Presentation

    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[0])
    title = slide.shapes.title
    if title:
        title.text = "Test Presentation Title"
    body = slide.placeholders[1]
    if hasattr(body, "text_frame"):
        body.text_frame.text = "First slide content"

    with tempfile.NamedTemporaryFile(suffix=".pptx", delete=False) as f:
        prs.save(f.name)
        temp_path = f.name

    try:
        yield temp_path
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)


@pytest.fixture
def temp_xlsx_file() -> Generator[str, None, None]:
    """Create a temporary XLSX file and clean it up after the test."""
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.title = "TestSheet"
    ws["A1"] = "Name"
    ws["B1"] = "Value"
    ws["A2"] = "Item1"
    ws["B2"] = 123

    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
        wb.save(f.name)
        temp_path = f.name

    try:
        yield temp_path
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)


class TestReadFile:
    """Tests for read_file function."""

    def test_read_txt_file(self) -> None:
        """Test reading a plain text file."""
        from agent_core.tools.course_tools import read_file

        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("This is a test document.")
            temp_path = f.name

        try:
            result = json.loads(read_file(temp_path))
            assert "content" in result
            assert result["content"] == "This is a test document."
            assert result["format"] == ".txt"
        finally:
            os.unlink(temp_path)

    def test_read_nonexistent_file(self) -> None:
        """Test reading a file that does not exist."""
        from agent_core.tools.course_tools import read_file

        # Use a path inside the temp directory (an allowed root) so the
        # allowlist check passes and we reach the "file not found" error.
        result = json.loads(
            read_file(os.path.join(tempfile.gettempdir(), "nonexistent_file.txt"))
        )
        assert "error" in result
        assert "File not found" in result["error"]

    def test_path_traversal_blocked(self) -> None:
        """Test that path traversal is blocked."""
        from agent_core.tools.course_tools import read_file

        result = json.loads(read_file("../../../etc/passwd"))
        assert "error" in result
        assert "Path traversal" in result["error"]

    def test_read_outside_allowed_roots(self) -> None:
        """Test that reading a file outside allowed directories is blocked."""
        from agent_core.tools.course_tools import read_file

        result = json.loads(read_file("/etc/hostname"))
        assert "error" in result
        assert "Access denied" in result["error"]

    def test_unsupported_format(self) -> None:
        """Test reading a file with unsupported format."""
        from agent_core.tools.course_tools import read_file

        with tempfile.NamedTemporaryFile(mode="w", suffix=".xyz", delete=False) as f:
            f.write("test content")
            temp_path = f.name

        try:
            result = json.loads(read_file(temp_path))
            assert "error" in result
            assert "Unsupported file format" in result["error"]
            assert ".xyz" in result["your_format"]
        finally:
            os.unlink(temp_path)

    def test_read_with_auto_doc_type(self) -> None:
        """Test reading with auto-detected doc type."""
        from agent_core.tools.course_tools import read_file

        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("# Test\n\nThis is markdown content.")
            temp_path = f.name

        try:
            result = json.loads(read_file(temp_path, doc_type="auto"))
            assert "content" in result
            assert result["format"] == ".md"
        finally:
            os.unlink(temp_path)


class TestReadBinaryFormats:
    """Tests for reading binary document formats."""

    def test_read_docx_file(self, temp_docx_file: str) -> None:
        """Test reading a DOCX file."""
        from agent_core.tools.course_tools import read_file

        result = json.loads(read_file(temp_docx_file))
        assert "content" in result
        assert "Word document test" in result["content"]
        assert result["format"] == ".docx"

    def test_read_pptx_file(self, temp_pptx_file: str) -> None:
        """Test reading a PPTX file."""
        from agent_core.tools.course_tools import read_file

        result = json.loads(read_file(temp_pptx_file))
        assert "content" in result
        assert "Test Presentation Title" in result["content"]
        assert "First slide content" in result["content"]
        assert result["format"] == ".pptx"

    def test_read_xlsx_file(self, temp_xlsx_file: str) -> None:
        """Test reading an XLSX file."""
        from agent_core.tools.course_tools import read_file

        result = json.loads(read_file(temp_xlsx_file))
        assert "content" in result
        assert "TestSheet" in result["content"]
        assert "Name" in result["content"]
        assert "Item1" in result["content"]
        assert result["format"] == ".xlsx"

    def test_read_html_file(self) -> None:
        """Test reading an HTML file."""
        from agent_core.tools.course_tools import read_file

        with tempfile.NamedTemporaryFile(mode="w", suffix=".html", delete=False) as f:
            f.write(
                "<html><body><h1>Test HTML</h1><p>Paragraph content</p></body></html>"
            )
            temp_path = f.name

        result = json.loads(read_file(temp_path))
        assert "content" in result
        assert "Test HTML" in result["content"]
        assert result["format"] == ".html"
        os.unlink(temp_path)

    def test_read_markdown_file(self) -> None:
        """Test reading a markdown file."""
        from agent_core.tools.course_tools import read_file

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".markdown", delete=False
        ) as f:
            f.write("# Markdown Title\n\nSome **bold** text and _italic_.")
            temp_path = f.name

        result = json.loads(read_file(temp_path))
        assert "content" in result
        assert "Markdown Title" in result["content"]
        assert result["format"] == ".markdown"
        os.unlink(temp_path)


class TestAnalyzeDocument:
    """Tests for analyze_document function."""

    def test_analyze_empty_content(self) -> None:
        """Test analyzing empty content."""
        from agent_core.tools.course_tools import analyze_document

        result = json.loads(analyze_document(summary="", key_points=[]))
        assert result["summary"] == "No summary provided."
        assert result["original_length"] == 0

    def test_analyze_normal_content(self) -> None:
        """Test analyzing normal text content."""
        from agent_core.tools.course_tools import analyze_document

        summary = "Python编程课程介绍"  # nosemgrep
        key_points = ["变量和数据类型", "控制流", "函数"]  # nosemgrep
        result = json.loads(
            analyze_document(
                summary=summary,
                key_points=key_points,
                doc_type="text",
                original_length=150,
            )
        )

        assert result["summary"] == summary
        assert result["key_points"] == key_points
        assert result["original_length"] == 150
        assert result["doc_type"] == "text"

    def test_analyze_with_doc_type(self) -> None:
        """Test analyzing with specific doc type."""
        from agent_core.tools.course_tools import analyze_document

        result = json.loads(
            analyze_document(
                summary="PDF content summary",
                key_points=["point1"],
                doc_type="pdf",
            )
        )

        assert result["doc_type"] == "pdf"

    def test_analyze_extracts_key_points(self) -> None:
        """Test that analyze_document formats key points correctly."""
        from agent_core.tools.course_tools import analyze_document

        key_points = ["First concept", "Second concept", "Third concept"]
        result = json.loads(
            analyze_document(
                summary="Test summary",
                key_points=key_points,
            )
        )

        assert isinstance(result["key_points"], list)
        assert result["key_points"] == key_points


class TestCourseToolsRegistration:
    """Tests for tool registration."""

    def test_course_tools_registered(self) -> None:
        """Test that course tools are registered in the tool registry."""
        from agent_core.tools.registry import ToolRegistry

        registry = ToolRegistry()
        # Import to trigger registration
        from agent_core.tools.course_tools import register_course_tools

        register_course_tools(registry)
        tools = registry.list_tools()
        tool_names = {t.name for t in tools}

        assert "read_file" in tool_names
        assert "analyze_document" in tool_names
