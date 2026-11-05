"""
OpenATS Document Text Extraction Module.
Provides stdlib-first text extraction for .txt, .md, .docx, and .pdf files
with optional adapters (pypdf, pdfplumber, PyPDF2, python-docx).
Author: Nazmul (@3447nazmul) | Repository: https://github.com/3447nazmul/openats
"""

import io
import os
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Union, Optional

# Maximum file size limit: 15 MB (matches the browser client limit)
MAX_FILE_SIZE_BYTES: int = 15 * 1024 * 1024

SUPPORTED_EXTENSIONS = (".txt", ".md", ".pdf", ".docx")


class ExtractionError(ValueError):
    """Raised when document extraction fails due to format, size, or unreadable content."""
    pass


def _word_count(text: str) -> int:
    return len(text.split()) if text else 0


def _extract_pdf_bytes(raw_bytes: bytes) -> str:
    """
    Extract text from PDF bytes page-by-page in reading order.
    Tries optional adapters in order: pypdf -> pdfplumber -> PyPDF2.
    """
    stream = io.BytesIO(raw_bytes)
    adapter_found = False
    pages_text = []

    # 1. Try pypdf
    try:
        import pypdf  # type: ignore
        adapter_found = True
        reader = pypdf.PdfReader(stream)
        for page in reader.pages:
            t = page.extract_text() or ""
            if t.strip():
                pages_text.append(t)
    except ImportError:
        pass
    except Exception as exc:
        raise ExtractionError(f"Failed to read PDF file: {exc}") from exc

    # 2. Try pdfplumber if pypdf was not installed
    if not adapter_found:
        try:
            import pdfplumber  # type: ignore
            adapter_found = True
            stream.seek(0)
            with pdfplumber.open(stream) as pdf:
                for page in pdf.pages:
                    t = page.extract_text() or ""
                    if t.strip():
                        pages_text.append(t)
        except ImportError:
            pass
        except Exception as exc:
            raise ExtractionError(f"Failed to read PDF file: {exc}") from exc

    # 3. Try PyPDF2 if neither pypdf nor pdfplumber was installed
    if not adapter_found:
        try:
            import PyPDF2  # type: ignore
            adapter_found = True
            stream.seek(0)
            reader = PyPDF2.PdfReader(stream)
            for page in reader.pages:
                t = page.extract_text() or ""
                if t.strip():
                    pages_text.append(t)
        except ImportError:
            pass
        except Exception as exc:
            raise ExtractionError(f"Failed to read PDF file: {exc}") from exc

    if not adapter_found:
        raise ExtractionError(
            "PDF extraction requires an optional PDF library. "
            'Install it with: pip install "openats[pdf]" (or pip install pypdf)'
        )

    full_text = "\n\n".join(pages_text).strip()
    if _word_count(full_text) < 20:
        raise ExtractionError(
            "No readable text found. This PDF looks scanned; use OCR or paste the text."
        )

    return full_text


def _extract_docx_stdlib(raw_bytes: bytes) -> str:
    """
    Zero-dependency stdlib DOCX text extractor.
    Unzips the archive and parses word/document.xml in document order,
    joining paragraphs with newlines and table row cells with ' | '.
    """
    stream = io.BytesIO(raw_bytes)
    if not zipfile.is_zipfile(stream):
        raise ExtractionError("Invalid .docx file: archive is not a valid ZIP container.")

    stream.seek(0)
    try:
        with zipfile.ZipFile(stream, "r") as zf:
            if "word/document.xml" not in zf.namelist():
                raise ExtractionError("Invalid .docx file: missing word/document.xml.")
            xml_bytes = zf.read("word/document.xml")
    except ExtractionError:
        raise
    except Exception as exc:
        raise ExtractionError(f"Failed to read .docx archive: {exc}") from exc

    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as exc:
        raise ExtractionError(f"Failed to parse .docx XML structure: {exc}") from exc

    def local_tag(elem) -> str:
        return elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag

    def extract_paragraph_text(p_elem) -> str:
        parts = []
        for node in p_elem.iter():
            t_name = local_tag(node)
            if t_name == "t" and node.text:
                parts.append(node.text)
            elif t_name == "tab":
                parts.append("\t")
            elif t_name in ("br", "cr"):
                parts.append("\n")
        return "".join(parts).strip()

    body = None
    for child in root:
        if local_tag(child) == "body":
            body = child
            break
    if body is None:
        body = root

    blocks = []
    for elem in body:
        t_name = local_tag(elem)
        if t_name == "p":
            p_text = extract_paragraph_text(elem)
            if p_text:
                blocks.append(p_text)
        elif t_name == "tbl":
            for row in elem:
                if local_tag(row) == "tr":
                    cells = []
                    for cell in row:
                        if local_tag(cell) == "tc":
                            cell_paras = [
                                extract_paragraph_text(p)
                                for p in cell
                                if local_tag(p) == "p"
                            ]
                            cell_str = " ".join(cp for cp in cell_paras if cp)
                            if cell_str:
                                cells.append(cell_str)
                    if cells:
                        blocks.append(" | ".join(cells))

    return "\n".join(blocks).strip()


def _extract_docx_bytes(raw_bytes: bytes) -> str:
    """
    Extract text from DOCX bytes.
    Prefers the zero-install stdlib XML parser first so DOCX always works out of the box,
    and falls back to python-docx if needed.
    """
    try:
        text = _extract_docx_stdlib(raw_bytes)
        if text:
            return text
    except ExtractionError:
        raise
    except Exception:
        pass

    # Optional fallback to python-docx if installed
    try:
        import docx  # type: ignore
        doc = docx.Document(io.BytesIO(raw_bytes))
        blocks = []
        for p in doc.paragraphs:
            if p.text and p.text.strip():
                blocks.append(p.text.strip())
        for table in doc.tables:
            for row in table.rows:
                cells = [c.text.strip() for c in row.cells if c.text and c.text.strip()]
                if cells:
                    blocks.append(" | ".join(cells))
        return "\n".join(blocks).strip()
    except ImportError:
        pass
    except Exception as exc:
        raise ExtractionError(f"Failed to extract text from .docx: {exc}") from exc

    return ""


def extract_text(
    path_or_bytes: Union[str, Path, bytes, bytearray],
    filename: Optional[str] = None,
) -> str:
    """
    Extract UTF-8 plain text from a file path or raw bytes (.txt, .md, .pdf, .docx).

    Args:
        path_or_bytes: File system path (str or Path) or raw file bytes.
        filename: Optional filename to determine extension when passing raw bytes.

    Returns:
        Extracted plain text string.

    Raises:
        FileNotFoundError: If a file path is given and does not exist.
        ExtractionError: If the file exceeds 15 MB, has an unsupported extension,
                         is a scanned/empty PDF, or cannot be parsed.
    """
    raw_bytes: bytes
    inferred_name: str

    if isinstance(path_or_bytes, (bytes, bytearray)):
        raw_bytes = bytes(path_or_bytes)
        inferred_name = filename or ""
        if len(raw_bytes) > MAX_FILE_SIZE_BYTES:
            raise ExtractionError(
                f"File size ({len(raw_bytes) / (1024 * 1024):.1f} MB) exceeds the 15 MB maximum limit."
            )
    elif isinstance(path_or_bytes, (str, Path)):
        path_str = str(path_or_bytes)
        inferred_name = filename or path_str
        if not os.path.exists(path_str):
            raise FileNotFoundError(f"File '{path_str}' not found.")
        file_size = os.path.getsize(path_str)
        if file_size > MAX_FILE_SIZE_BYTES:
            raise ExtractionError(
                f"File '{os.path.basename(path_str)}' ({file_size / (1024 * 1024):.1f} MB) "
                "exceeds the 15 MB maximum limit."
            )
        with open(path_str, "rb") as f:
            raw_bytes = f.read()
    else:
        raise ExtractionError(f"Unsupported input type: {type(path_or_bytes).__name__}")

    ext = os.path.splitext(inferred_name)[1].lower()
    if ext not in SUPPORTED_EXTENSIONS:
        supported_list = ", ".join(SUPPORTED_EXTENSIONS)
        raise ExtractionError(
            f"Unsupported file format '{ext or 'unknown'}'. "
            f"Supported formats are: {supported_list}"
        )

    if ext in (".txt", ".md"):
        try:
            return raw_bytes.decode("utf-8")
        except UnicodeDecodeError:
            return raw_bytes.decode("utf-8", errors="replace")

    if ext == ".pdf":
        return _extract_pdf_bytes(raw_bytes)

    if ext == ".docx":
        return _extract_docx_bytes(raw_bytes)

    raise ExtractionError(f"Unsupported file format '{ext}'.")
