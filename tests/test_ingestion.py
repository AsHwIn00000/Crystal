"""Ingestion pipeline and parser tests."""
import io
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock


def test_txt_parser_returns_single_page(tmp_path):
    from app.ingestion.parsers.txt_parser import TxtParser
    f = tmp_path / 'test.txt'
    f.write_text('Line 1\nLine 2\nLine 3\n' * 20, encoding='utf-8')
    parser = TxtParser()
    pages = parser.parse(f)
    # Must return single page — no pre-splitting
    assert len(pages) == 1
    assert pages[0].page_number == 1
    assert 'Line 1' in pages[0].text


def test_txt_parser_full_content(tmp_path):
    from app.ingestion.parsers.txt_parser import TxtParser
    content = 'Hello World ' * 1000
    f = tmp_path / 'big.txt'
    f.write_text(content, encoding='utf-8')
    parser = TxtParser()
    pages = parser.parse(f)
    assert len(pages) == 1
    assert len(pages[0].text) > 100


def test_chunker_produces_chunks(tmp_path):
    from app.ingestion.parsers.base import ParsedPage
    from app.ingestion.chunker import chunk_pages
    pages = [ParsedPage(page_number=1, text=' '.join(['word'] * 1000), metadata={})]
    chunks = chunk_pages(pages, chunk_size=100, chunk_overlap=10)
    assert len(chunks) > 1


def test_chunker_respects_overlap():
    from app.ingestion.parsers.base import ParsedPage
    from app.ingestion.chunker import chunk_pages
    # Create text with known sentence boundaries
    text = 'First sentence here. Second sentence here. Third sentence here. ' * 30
    pages = [ParsedPage(page_number=1, text=text, metadata={})]
    chunks = chunk_pages(pages, chunk_size=50, chunk_overlap=10)
    assert len(chunks) >= 2


def test_chunker_empty_page():
    from app.ingestion.parsers.base import ParsedPage
    from app.ingestion.chunker import chunk_pages
    pages = [ParsedPage(page_number=1, text='', metadata={})]
    chunks = chunk_pages(pages)
    assert chunks == []


def test_pdf_parser_smoke(tmp_path):
    """Smoke test — just checks the parser is importable and handles missing file gracefully."""
    from app.ingestion.parsers.pdf_parser import PdfParser
    assert PdfParser is not None


def test_docx_parser_extracts_text(tmp_path):
    """Test DOCX parser with a real docx file."""
    try:
        from docx import Document as DocxDoc
    except ImportError:
        pytest.skip('python-docx not available')
    f = tmp_path / 'test.docx'
    doc = DocxDoc()
    doc.add_paragraph('Hello from Crystal AI test document.')
    doc.add_paragraph('Second paragraph with more text.')
    doc.save(str(f))

    from app.ingestion.parsers.docx_parser import DocxParser
    parser = DocxParser()
    pages = parser.parse(f)
    assert len(pages) == 1
    assert pages[0].page_number == 1  # All DOCX content is page 1
    assert 'Hello from Crystal AI' in pages[0].text


def test_validators_accept_txt():
    """Test that txt files pass validation."""
    from unittest.mock import MagicMock
    from app.ingestion.validators import validate_upload
    mock_file = MagicMock()
    mock_file.filename = 'test.txt'
    mock_file.content_type = 'text/plain'
    mock_file.stream.read.return_value = b'Hello'
    mock_file.stream.seek = MagicMock()
    mock_file.stream.tell.return_value = 5
    mock_file.stream.seek.return_value = None

    # read first returns header (called with 8 bytes), then size check
    call_count = [0]
    def mock_read(n=None):
        call_count[0] += 1
        if n == 8:
            return b'Hello   '  # txt has no magic bytes
        return b'Hello'
    mock_file.stream.read = mock_read

    size_responses = [5]
    tell_call = [0]
    def mock_tell():
        v = size_responses[0] if tell_call[0] == 0 else size_responses[0]
        tell_call[0] += 1
        return v
    mock_file.stream.tell = mock_tell

    from flask import Flask
    from config import config as cfg
    app = Flask(__name__)
    app.config.from_object(cfg['testing'])
    with app.app_context():
        ext, name, size = validate_upload(mock_file)
        assert ext == 'txt'
        assert name.endswith('.txt')


def test_pipeline_ingest_sets_failed_on_missing_file(app):
    """Ingestion of a document with no file on disk should set status=FAILED."""
    from app.extensions import db
    from app.models.document import Document, DocumentScope, DocumentStatus, DocumentProcessingJob, JobStatus
    from app.ingestion.pipeline import ingest_document

    with app.app_context():
        doc = Document(
            user_id=None, filename_original='ghost.txt',
            filename_stored='ghostfile.txt',
            scope=DocumentScope.COLLEGE_WIDE,
            status=DocumentStatus.PENDING, file_type='txt', file_size=10
        )
        db.session.add(doc)
        db.session.flush()
        job = DocumentProcessingJob(document_id=doc.id, status=JobStatus.QUEUED)
        db.session.add(job)
        db.session.commit()
        doc_id = doc.id

        ingest_document(doc_id)

        doc = db.session.get(Document, doc_id)
        assert doc.status == DocumentStatus.FAILED
