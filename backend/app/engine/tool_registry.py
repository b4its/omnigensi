import os
import base64
from pathlib import Path
from typing import List, Dict, Any, Union
from langchain_core.tools import tool
from docx import Document
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

from app.core.security import sanitize_workspace_path
from app.core.config import settings
from app.engine.mcp_bridge import mcp_manager


@tool
def create_markdown_document(filename: str, content: str) -> Dict[str, Any]:
    """
    Creates or updates a Markdown (.md) document in the local workspace directory.
    Use this tool to save technical documentation, reports, specifications, notes, or code to local disk.
    Args:
        filename: Name of the file, e.g. 'architecture_spec.md'
        content: Markdown string content
    """
    if not filename.endswith(".md"):
        filename = f"{filename}.md"
    
    target_path = sanitize_workspace_path(filename)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    
    target_path.write_text(content, encoding="utf-8")
    encoded_b64 = base64.b64encode(content.encode("utf-8")).decode("utf-8")
    size_bytes = target_path.stat().st_size

    return {
        "status": "success",
        "action": "device_file_write",
        "filename": target_path.name,
        "filepath": str(target_path),
        "file_type": "markdown",
        "mime_type": "text/markdown",
        "size_bytes": size_bytes,
        "content_base64": encoded_b64,
        "message": f"Successfully created Markdown file '{target_path.name}' ({size_bytes} bytes)",
    }


@tool
def create_word_document(filename: str, title: str, sections: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Creates a formatted Microsoft Word (.docx) document in the local workspace directory.
    Args:
        filename: File name ending with .docx (e.g. 'Executive_Summary.docx')
        title: Main Document Title heading
        sections: List of section dicts, e.g. [{"heading": "Introduction", "body": "...", "bullets": ["A", "B"]}]
    """
    if not filename.endswith(".docx"):
        filename = f"{filename}.docx"

    target_path = sanitize_workspace_path(filename)
    target_path.parent.mkdir(parents=True, exist_ok=True)

    doc = Document()
    doc.add_heading(title, level=0)

    for sec in sections:
        h = sec.get("heading")
        if h:
            doc.add_heading(str(h), level=1)
        b = sec.get("body")
        if b:
            doc.add_paragraph(str(b))
        bullets = sec.get("bullets", [])
        if isinstance(bullets, list):
            for bullet in bullets:
                doc.add_paragraph(str(bullet), style="List Bullet")
        table_data = sec.get("table")
        if isinstance(table_data, list) and len(table_data) > 0:
            cols = len(table_data[0]) if isinstance(table_data[0], list) else 1
            table = doc.add_table(rows=len(table_data), cols=cols)
            for row_idx, row in enumerate(table_data):
                if isinstance(row, list):
                    for col_idx, cell_value in enumerate(row):
                        table.cell(row_idx, col_idx).text = str(cell_value)

    doc.save(str(target_path))
    file_bytes = target_path.read_bytes()
    encoded_b64 = base64.b64encode(file_bytes).decode("utf-8")
    size_bytes = len(file_bytes)

    return {
        "status": "success",
        "action": "device_file_write",
        "filename": target_path.name,
        "filepath": str(target_path),
        "file_type": "docx",
        "mime_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "size_bytes": size_bytes,
        "content_base64": encoded_b64,
        "message": f"Successfully created Word document '{target_path.name}' ({size_bytes} bytes)",
    }


@tool
def create_pdf_document(filename: str, title: str, body_text: str) -> Dict[str, Any]:
    """
    Creates a styled PDF document in the local workspace directory.
    Args:
        filename: File name ending with .pdf (e.g. 'Audit_Report.pdf')
        title: Main report heading
        body_text: Paragraph text (newlines will create separate paragraphs)
    """
    if not filename.endswith(".pdf"):
        filename = f"{filename}.pdf"

    target_path = sanitize_workspace_path(filename)
    target_path.parent.mkdir(parents=True, exist_ok=True)

    doc = SimpleDocTemplate(str(target_path), pagesize=letter)
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "CyberpunkTitle",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=20,
        leading=24,
        textColor=colors.HexColor("#0048E5"),
        spaceAfter=15,
    )
    body_style = ParagraphStyle(
        "CyberpunkBody",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=10,
        leading=14,
        textColor=colors.HexColor("#111827"),
        spaceAfter=8,
    )

    story = [
        Paragraph(title, title_style),
        Spacer(1, 12),
    ]

    for para in body_text.split("\n\n"):
        para = para.strip()
        if para:
            clean_para = para.replace("<", "&lt;").replace(">", "&gt;").replace("\n", "<br/>")
            story.append(Paragraph(clean_para, body_style))
            story.append(Spacer(1, 6))

    doc.build(story)
    file_bytes = target_path.read_bytes()
    encoded_b64 = base64.b64encode(file_bytes).decode("utf-8")
    size_bytes = len(file_bytes)

    return {
        "status": "success",
        "action": "device_file_write",
        "filename": target_path.name,
        "filepath": str(target_path),
        "file_type": "pdf",
        "mime_type": "application/pdf",
        "size_bytes": size_bytes,
        "content_base64": encoded_b64,
        "message": f"Successfully created PDF report '{target_path.name}' ({size_bytes} bytes)",
    }


@tool
def create_code_file(filename: str, code: str, language: str = "") -> Dict[str, Any]:
    """
    Creates or updates a source code, script, or configuration file in the local workspace directory.
    Supports Python (.py), TypeScript (.ts), JavaScript (.js), Shell (.sh), SQL (.sql), JSON (.json), YAML (.yaml), etc.
    Args:
        filename: Name of the script/file with extension, e.g. 'pipeline.py', 'schema.sql', 'agent.ts'
        code: Source code or configuration text
        language: Optional language name or syntax tag, e.g. 'python', 'typescript', 'bash'
    """
    ext_mime_map = {
        ".py": "text/x-python",
        ".ts": "application/typescript",
        ".js": "application/javascript",
        ".sh": "application/x-sh",
        ".bash": "application/x-sh",
        ".sql": "application/sql",
        ".json": "application/json",
        ".yaml": "text/yaml",
        ".yml": "text/yaml",
        ".html": "text/html",
        ".css": "text/css",
        ".rs": "text/rust",
        ".go": "text/x-go",
        ".c": "text/x-c",
        ".cpp": "text/x-c++",
    }
    
    target_path = sanitize_workspace_path(filename)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    
    target_path.write_text(code, encoding="utf-8")
    encoded_b64 = base64.b64encode(code.encode("utf-8")).decode("utf-8")
    size_bytes = target_path.stat().st_size
    file_ext = target_path.suffix.lower()
    
    mime_type = ext_mime_map.get(file_ext, "text/plain")
    inferred_lang = language.lower() if language else file_ext.lstrip(".") or "text"

    return {
        "status": "success",
        "action": "device_file_write",
        "filename": target_path.name,
        "filepath": str(target_path),
        "file_type": "code",
        "language": inferred_lang,
        "mime_type": mime_type,
        "size_bytes": size_bytes,
        "content_base64": encoded_b64,
        "message": f"Successfully created {inferred_lang} code file '{target_path.name}' ({size_bytes} bytes)",
    }


@tool
def read_local_workspace_file(filename: str) -> Dict[str, Any]:
    """
    Reads the content of a local file inside the workspace folder.
    Args:
        filename: Relative path or filename in workspace
    """
    try:
        target_path = sanitize_workspace_path(filename)
        if not target_path.exists() or not target_path.is_file():
            return {"status": "error", "message": f"File '{filename}' does not exist"}
        
        content = target_path.read_text(encoding="utf-8", errors="replace")
        return {
            "status": "success",
            "filename": target_path.name,
            "filepath": str(target_path),
            "content": content[:50000],  # safety cap
            "size_bytes": target_path.stat().st_size,
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


@tool
def list_local_workspace_files(subdirectory: str = ".") -> Dict[str, Any]:
    """
    Lists files and directories inside the local workspace sandbox.
    Args:
        subdirectory: Subdirectory relative to workspace, defaults to '.'
    """
    try:
        target_path = sanitize_workspace_path(subdirectory)
        if not target_path.exists() or not target_path.is_dir():
            return {"status": "error", "message": f"Directory '{subdirectory}' does not exist"}

        items = []
        for entry in os.scandir(target_path):
            items.append({
                "name": entry.name,
                "is_dir": entry.is_dir(),
                "size_bytes": entry.stat().st_size if entry.is_file() else 0,
            })
        return {
            "status": "success",
            "directory": subdirectory,
            "items": sorted(items, key=lambda x: (not x["is_dir"], x["name"])),
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


@tool
def mcp_read_file(path: str) -> Dict[str, Any]:
    """
    [Model Context Protocol] Reads the full content of a file on the local filesystem.
    Args:
        path: Relative workspace file path
    """
    return read_local_workspace_file.invoke({"filename": path})


@tool
def mcp_write_file(path: str, content: str) -> Dict[str, Any]:
    """
    [Model Context Protocol] Writes or creates a file on the local filesystem.
    Args:
        path: Target file path
        content: Text or code to write
    """
    return create_markdown_document.invoke({"filename": path, "content": content})


@tool
def mcp_list_directory(path: str = ".") -> Dict[str, Any]:
    """
    [Model Context Protocol] Lists files and directories in a local workspace path.
    Args:
        path: Directory path, defaults to '.'
    """
    return list_local_workspace_files.invoke({"subdirectory": path})


@tool
def mcp_create_entities(entities: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    [Model Context Protocol] Stores knowledge entities and relations in the persistent MCP Memory graph.
    Args:
        entities: List of entity objects with name, entityType, and observations
    """
    # There is no real memory backend wired up yet. Reporting success here
    # would let the model believe it persisted knowledge that was discarded.
    return {
        "status": "error",
        "action": "mcp_memory_sync",
        "message": (
            "No MCP memory server is connected. Entities were NOT persisted. "
            "Register a memory MCP server to enable graph storage."
        ),
        "entities_count": 0,
        "entities_received": len(entities),
    }


@tool
def mcp_read_graph() -> Dict[str, Any]:
    """
    [Model Context Protocol] Reads current knowledge nodes and relationships from MCP Memory graph.
    """
    # Returning hardcoded "entities" made an empty graph look populated.
    return {
        "status": "error",
        "action": "mcp_memory_read",
        "message": (
            "No MCP memory server is connected. The knowledge graph is empty; "
            "Nothing was read."
        ),
        "entities": [],
    }


DEVICE_TOOL_MAP = {
    "create_markdown_document": create_markdown_document,
    "create_word_document": create_word_document,
    "create_pdf_document": create_pdf_document,
    "create_code_file": create_code_file,
    "read_local_workspace_file": read_local_workspace_file,
    "list_local_workspace_files": list_local_workspace_files,
    "mcp_read_file": mcp_read_file,
    "mcp_write_file": mcp_write_file,
    "mcp_list_directory": mcp_list_directory,
    "mcp_create_entities": mcp_create_entities,
    "mcp_read_graph": mcp_read_graph,
}

AVAILABLE_TOOLS_METADATA = [
    {
        "id": "create_markdown_document",
        "name": "Markdown Generator (.md)",
        "description": "Writes structured Markdown reports, technical documentation, or notes directly to local storage.",
        "icon": "file-text",
        "category": "document",
        "extension": ".md",
        "requires_write": True,
    },
    {
        "id": "create_code_file",
        "name": "Code Script Builder (.py, .ts, .sh, .json)",
        "description": "Writes production-grade source code, scripts, configuration, or SQL files directly to local workspace.",
        "icon": "code",
        "category": "code",
        "extension": "*",
        "requires_write": True,
    },
    {
        "id": "create_word_document",
        "name": "Word Document Builder (.docx)",
        "description": "Builds formatted Microsoft Word files with headings, paragraphs, bullet points, and tables.",
        "icon": "file-code",
        "category": "document",
        "extension": ".docx",
        "requires_write": True,
    },
    {
        "id": "create_pdf_document",
        "name": "PDF Report Generator (.pdf)",
        "description": "Renders styled PDF documents ready for distribution and printing.",
        "icon": "file",
        "category": "document",
        "extension": ".pdf",
        "requires_write": True,
    },
    {
        "id": "read_local_workspace_file",
        "name": "Local Workspace Reader",
        "description": "Allows the agent to read and analyze existing text, script, or config files from local project folder.",
        "icon": "book-open",
        "category": "filesystem",
        "extension": "*",
        "requires_write": False,
    },
    {
        "id": "list_local_workspace_files",
        "name": "Local Workspace Explorer",
        "description": "Enables the agent to inspect folder structures and file names in the workspace.",
        "icon": "folder-search",
        "category": "filesystem",
        "extension": "*",
        "requires_write": False,
    },
    {
        "id": "mcp_read_file",
        "name": "MCP: File Reader",
        "description": "Model Context Protocol interface to read system and workspace documents.",
        "icon": "network",
        "category": "mcp",
        "extension": "*",
        "requires_write": False,
    },
    {
        "id": "mcp_write_file",
        "name": "MCP: File Writer",
        "description": "Model Context Protocol interface to persist files through host-level MCP servers.",
        "icon": "network",
        "category": "mcp",
        "extension": "*",
        "requires_write": True,
    },
    {
        "id": "mcp_list_directory",
        "name": "MCP: Directory Lister",
        "description": "Model Context Protocol server directory traversal.",
        "icon": "folder-tree",
        "category": "mcp",
        "extension": "*",
        "requires_write": False,
    },
    {
        "id": "mcp_create_entities",
        "name": "MCP: Memory Entity Store",
        "description": "Inserts concepts and relations into persistent MCP graph memory.",
        "icon": "cpu",
        "category": "mcp",
        "extension": "graph",
        "requires_write": True,
    },
    {
        "id": "mcp_read_graph",
        "name": "MCP: Memory Graph Query",
        "description": "Queries persistent knowledge graph nodes from the MCP memory server.",
        "icon": "cpu",
        "category": "mcp",
        "extension": "graph",
        "requires_write": False,
    },
]
