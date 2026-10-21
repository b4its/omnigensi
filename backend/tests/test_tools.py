from pathlib import Path
from app.engine.tool_registry import (
    create_markdown_document,
    create_word_document,
    create_pdf_document,
    create_code_file,
    read_local_workspace_file,
    list_local_workspace_files,
)


def test_create_markdown_document():
    res = create_markdown_document.invoke({
        "filename": "unit_test_spec.md",
        "content": "# Test Header\n\nAutomated unit test markdown content.",
    })
    assert res["status"] == "success"
    assert res["filename"] == "unit_test_spec.md"
    assert res["file_type"] == "markdown"
    assert res["size_bytes"] > 0
    assert len(res["content_base64"]) > 0
    assert Path(res["filepath"]).exists()


def test_create_word_document():
    res = create_word_document.invoke({
        "filename": "unit_test_doc.docx",
        "title": "Unit Test Document",
        "sections": [
            {"heading": "Section 1", "body": "Body paragraph content", "bullets": ["A", "B"]},
        ],
    })
    assert res["status"] == "success"
    assert res["filename"] == "unit_test_doc.docx"
    assert res["file_type"] == "docx"
    assert res["size_bytes"] > 1000
    assert Path(res["filepath"]).exists()


def test_create_pdf_document():
    res = create_pdf_document.invoke({
        "filename": "unit_test_report.pdf",
        "title": "Unit Test PDF Report",
        "body_text": "First paragraph.\n\nSecond paragraph with styled text.",
    })
    assert res["status"] == "success"
    assert res["filename"] == "unit_test_report.pdf"
    assert res["file_type"] == "pdf"
    assert res["size_bytes"] > 500
    assert Path(res["filepath"]).exists()


def test_read_and_list_workspace_files():
    list_res = list_local_workspace_files.invoke({"subdirectory": "."})
    assert list_res["status"] == "success"
    assert isinstance(list_res["items"], list)
    assert len(list_res["items"]) > 0

    read_res = read_local_workspace_file.invoke({"filename": "unit_test_spec.md"})
    assert read_res["status"] == "success"
    assert "# Test Header" in read_res["content"]


def test_create_code_file():
    code_content = "def calculate_hash(data: str) -> str:\n    return f'hash_{len(data)}'\n"
    res = create_code_file.invoke({
        "filename": "pipeline_generator.py",
        "code": code_content,
        "language": "python",
    })
    assert res["status"] == "success"
    assert res["filename"] == "pipeline_generator.py"
    assert res["file_type"] == "code"
    assert res["language"] == "python"
    assert res["mime_type"] == "text/x-python"
    assert res["size_bytes"] == len(code_content.encode("utf-8"))
    assert Path(res["filepath"]).exists()
    assert Path(res["filepath"]).read_text(encoding="utf-8") == code_content
