from io import BytesIO

import pytest
from pypdf import PdfReader, PdfWriter

from app.rag.document_processor import DocumentProcessingError, chunk_pages, extract_pdf_pages, PageText


def test_extract_pdf_pages_preserves_page_numbers():
    writer = PdfWriter()
    writer.add_blank_page(width=300, height=300)
    buffer = BytesIO()
    writer.write(buffer)
    # A blank PDF is valid but has no extractable text.
    with pytest.raises(DocumentProcessingError, match="no extractable text"):
        extract_pdf_pages(buffer.getvalue())


def test_chunking_preserves_source_metadata():
    chunks = chunk_pages([PageText(page=3, text="hello " * 500)], "requirements.pdf", chunk_size=120)
    assert chunks
    assert all(chunk.page == 3 for chunk in chunks)
    assert all(chunk.filename == "requirements.pdf" for chunk in chunks)
    assert all(chunk.source == "requirements.pdf page 3" for chunk in chunks)


def test_rejects_non_pdf_content():
    with pytest.raises(DocumentProcessingError, match="valid PDF"):
        extract_pdf_pages(b"not a pdf")


# ---------------------------------------------------------------------------
# Structure-aware chunking
# ---------------------------------------------------------------------------

def _legacy_chunks(pages, filename, chunk_size=1400, overlap=220):
    """Reference copy of the original fixed-size, page-bounded chunking."""
    out = []
    for page in pages:
        text = " ".join(page.text.split())
        start = 0
        while start < len(text):
            end = min(len(text), start + chunk_size)
            piece = text[start:end].strip()
            if piece:
                out.append((page.page, piece))
            if end >= len(text):
                break
            start = max(end - overlap, start + 1)
    return out


def _page_chunks(chunks, page):
    return [c for c in chunks if c.page == page]


def test_documents_with_headings_split_at_section_boundaries():
    page = PageText(
        page=1,
        text=(
            "1. Introduction\n"
            "This document describes the system.\n"
            "3.1 Customer Registration\n"
            "The system shall let customers register with an email address.\n"
            "3.2 Account Verification\n"
            "The system shall send a verification code by SMS.\n"
        ),
    )
    chunks = chunk_pages([page], "srs.pdf")

    assert [c.section for c in chunks] == ["1. Introduction", "3.1 Customer Registration", "3.2 Account Verification"]
    assert chunks[0].text == "1. Introduction\nThis document describes the system."
    assert chunks[1].text.startswith("3.1 Customer Registration\n")
    assert "register with an email" in chunks[1].text
    # Sections do not bleed into each other.
    assert "verification code" not in chunks[1].text
    assert "register" not in chunks[2].text


def test_documents_without_headings_match_original_chunking():
    long_text = "The system shall process requests quickly and reliably. " * 80
    pages = [
        PageText(page=1, text="Just a paragraph with no numbering at all."),
        PageText(page=2, text=long_text),
        PageText(page=4, text="Multiple\nshort\nlines\nof\nplain text"),
    ]
    chunks = chunk_pages(pages, "plain.pdf")

    assert [(c.page, c.text) for c in chunks] == _legacy_chunks(pages, "plain.pdf")
    assert all(c.section is None for c in chunks)


def test_non_heading_numbered_lines_fall_back_safely():
    text = "\n".join(
        [
            "1. enter your email address",  # list item, lowercase words
            "2. Click the submit button to continue with the process.",  # sentence
            "3.1 Customer Registration ........ 12",  # table-of-contents leader
            "REQ-001 The system shall log every failed login attempt.",
            "2024 was the year the project started.",
        ]
    )
    pages = [PageText(page=1, text=text)]
    chunks = chunk_pages(pages, "plain.pdf")

    assert [(c.page, c.text) for c in chunks] == _legacy_chunks(pages, "plain.pdf")
    assert all(c.section is None for c in chunks)


def test_mixed_heading_and_no_heading_pages():
    pages = [
        PageText(page=1, text="Software Requirements Specification\nAcme Corp, version 1.0"),
        PageText(page=2, text="3.1 Customer Registration\nCustomers register with an email."),
        PageText(page=3, text="Continuation text of the registration flow with no heading at all."),
        PageText(page=4, text="Leading text before any heading on this page.\n4.2 Payments\nPayments use cards."),
    ]
    chunks = chunk_pages(pages, "mixed.pdf")

    # Pages without a heading are chunked exactly as before: no prefix, nothing dropped.
    legacy = _legacy_chunks(pages, "mixed.pdf")
    for page_number in (1, 3):
        assert [c.text for c in _page_chunks(chunks, page_number)] == [t for p, t in legacy if p == page_number]
        assert all(c.section is None for c in _page_chunks(chunks, page_number))

    assert [c.section for c in _page_chunks(chunks, 2)] == ["3.1 Customer Registration"]
    assert _page_chunks(chunks, 2)[0].text.startswith("3.1 Customer Registration\n")

    # Page 4: leading text stays plain, the heading section is prefixed.
    page4 = _page_chunks(chunks, 4)
    assert [c.section for c in page4] == [None, "4.2 Payments"]
    assert page4[0].text == "Leading text before any heading on this page."
    assert page4[1].text == "4.2 Payments\nPayments use cards."


def test_oversized_section_is_split_with_overlap_and_keeps_heading():
    heading = "3.1 Customer Registration"
    body = "x" * 4000
    chunks = chunk_pages([PageText(page=7, text=f"{heading}\n{body}")], "big.pdf")

    assert len(chunks) > 1
    assert all(c.text.startswith(f"{heading}\n") for c in chunks)
    assert all(c.section == heading for c in chunks)
    assert all(len(c.text) <= 1400 for c in chunks)

    pieces = [c.text[len(heading) + 1:] for c in chunks]
    for previous, following in zip(pieces, pieces[1:]):
        assert previous[-220:] == following[:220]  # 220-character overlap preserved
    # Every character of the section body is still covered.
    covered = len(pieces[0]) + sum(len(p) - 220 for p in pieces[1:])
    assert covered == len(body)


def test_oversized_unheaded_page_still_uses_plain_windows():
    page = PageText(page=2, text="y" * 3000)
    chunks = chunk_pages([page], "plain.pdf")
    assert [c.text for c in chunks] == [t for _, t in _legacy_chunks([page], "plain.pdf")]
    assert all(len(c.text) <= 1400 for c in chunks)


def test_heading_without_body_is_kept():
    chunks = chunk_pages([PageText(page=1, text="5.4 Future Enhancements")], "srs.pdf")
    assert len(chunks) == 1
    assert chunks[0].text == "5.4 Future Enhancements"
    assert chunks[0].section == "5.4 Future Enhancements"


def test_metadata_and_page_boundaries_are_preserved():
    pages = [
        PageText(page=2, text="2.1 Overview\n" + "alpha " * 400),
        PageText(page=5, text="no heading here " * 100),
        PageText(page=9, text="6.3 Reporting\nbeta text " + "z" * 2000),
    ]
    chunks = chunk_pages(pages, "spec.pdf")

    assert [c.index for c in chunks] == list(range(len(chunks)))  # unique, sequential ids
    for chunk in chunks:
        assert chunk.filename == "spec.pdf"
        assert chunk.source == f"spec.pdf page {chunk.page}"
    assert {c.page for c in chunks} == {2, 5, 9}
    # Chunks never mix text from different pages.
    assert all("alpha" not in c.text for c in chunks if c.page != 2)
    assert all("beta" not in c.text and "Reporting" not in c.text for c in chunks if c.page != 9)
    assert all("no heading here" not in c.text for c in chunks if c.page != 5)
    # Page order is preserved.
    assert [c.page for c in chunks] == sorted(c.page for c in chunks)
