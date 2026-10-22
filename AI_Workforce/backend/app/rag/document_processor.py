import re
from collections.abc import Iterator
from dataclasses import dataclass
from io import BytesIO

from pypdf import PdfReader


class DocumentProcessingError(ValueError):
    pass


@dataclass
class PageText:
    page: int
    text: str


@dataclass
class TextChunk:
    index: int
    page: int
    text: str
    filename: str
    source: str
    section: str | None = None


def extract_pdf_pages(content: bytes) -> list[PageText]:
    if not content.startswith(b"%PDF"):
        raise DocumentProcessingError("The uploaded file is not a valid PDF.")
    try:
        reader = PdfReader(BytesIO(content))
        pages: list[PageText] = []
        for page_number, page in enumerate(reader.pages, start=1):
            text = (page.extract_text() or "").strip()
            if text:
                pages.append(PageText(page=page_number, text=text))
        if not pages:
            raise DocumentProcessingError("The PDF contains no extractable text.")
        return pages
    except DocumentProcessingError:
        raise
    except Exception as exc:
        raise DocumentProcessingError(f"Could not read the PDF: {exc}") from exc


# --- Structure-aware chunking -------------------------------------------------
# Numbered SRS headings such as "3.1 Customer Registration" or "2. Overall Description".
_HEADING_RE = re.compile(r"^(\d{1,2}(?:\.\d{1,2}){0,4})\.?\s+(\S.*)$")
_MAX_HEADING_CHARS = 100


def _is_heading(line: str) -> bool:
    """Conservative check for a numbered SRS heading on a single line.

    Prefers missing a heading (safe fallback to fixed-size chunks) over treating
    ordinary sentences or list items as headings.
    """
    if len(line) > _MAX_HEADING_CHARS or "...." in line:  # long lines / table-of-contents leaders
        return False
    match = _HEADING_RE.match(line)
    if not match:
        return False
    number, title = match.groups()
    if not title[0].isupper() or title[-1] in ".,;!?":
        return False
    words = title.split()
    if len(words) > 12:
        return False
    if "." not in number:
        # "1. Introduction" can also be a numbered list item ("1. Enter your email"),
        # so single-level numbers must look like a Title Case heading.
        if len(words) > 8:
            return False
        for word in words:
            if len(word) > 3 and word[0].isalpha() and not word[0].isupper():
                return False
    return True


def _split_sections(text: str) -> list[tuple[str | None, str]]:
    """Split one page into (heading, body) sections at detected headings.

    Text before the first heading on the page has heading None. A page without any
    heading comes back as a single (None, whole_page) section.
    """
    sections: list[tuple[str | None, str]] = []
    heading: str | None = None
    body: list[str] = []

    def flush() -> None:
        normalized = " ".join(" ".join(body).split())
        if heading is not None or normalized:
            sections.append((heading, normalized))

    for raw_line in text.splitlines():
        line = " ".join(raw_line.split())
        if line and _is_heading(line):
            flush()
            heading, body = line, []
        elif line:
            body.append(line)
    flush()
    return sections


def _windows(text: str, chunk_size: int, overlap: int) -> Iterator[str]:
    """Fixed-size windows with overlap (the original chunking logic)."""
    start = 0
    while start < len(text):
        end = min(len(text), start + chunk_size)
        chunk_text = text[start:end].strip()
        if chunk_text:
            yield chunk_text
        if end >= len(text):
            break
        start = max(end - overlap, start + 1)


def chunk_pages(pages: list[PageText], filename: str, chunk_size: int = 1400, overlap: int = 220) -> list[TextChunk]:
    """Chunk pages, splitting at numbered SRS headings when present.

    - Chunks never cross page boundaries; page/filename/source metadata is unchanged.
    - Text under a detected heading is prefixed with that heading. Sections larger than
      chunk_size are split with the usual window + overlap, each piece keeping the prefix.
    - Pages (or leading text on a page) with no heading use the original fixed-size
      chunking with no prefix.
    """
    chunks: list[TextChunk] = []

    def add(page: PageText, text: str, section: str | None) -> None:
        chunks.append(
            TextChunk(
                index=len(chunks),
                page=page.page,
                text=text,
                filename=filename,
                source=f"{filename} page {page.page}",
                section=section,
            )
        )

    for page in pages:
        for heading, body in _split_sections(page.text):
            if heading is None:
                for piece in _windows(body, chunk_size, overlap):
                    add(page, piece, None)
                continue
            if not body:  # heading with no text under it: keep it rather than drop it
                add(page, heading, heading)
                continue
            prefix = f"{heading}\n"
            size = max(chunk_size - len(prefix), chunk_size // 2, 1)
            for piece in _windows(body, size, overlap):
                add(page, prefix + piece, heading)
    return chunks
