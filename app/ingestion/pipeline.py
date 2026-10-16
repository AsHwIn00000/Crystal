import json
import shutil
import logging
from datetime import datetime, timezone
from pathlib import Path
from flask import current_app

from app.extensions import db
from app.models.document import (
    Document, DocumentChunk, DocumentProcessingJob,
    DocumentScope, DocumentStatus, JobStatus
)
from app.ingestion.parsers import parser_for
from app.ingestion import chunker

logger = logging.getLogger(__name__)

OCR_AVAILABLE = shutil.which('tesseract') is not None


def _resolve_file_path(doc: Document) -> Path:
    """Reconstruct the full disk path for a Document's stored file.

    Must match the directory layout used by the upload routes:
      - PRIVATE documents: UPLOAD_FOLDER/private/<user_id>/<filename_stored>
      - COLLEGE_WIDE documents: UPLOAD_FOLDER/college_wide/<filename_stored>
    """
    upload_folder = Path(current_app.config['UPLOAD_FOLDER'])
    if doc.scope == DocumentScope.PRIVATE:
        return upload_folder / 'private' / str(doc.user_id) / doc.filename_stored
    else:  # COLLEGE_WIDE
        return upload_folder / 'college_wide' / doc.filename_stored


def ingest_document(document_id: int):
    """Orchestrate document ingestion. Called by ThreadPoolJobRunner inside an app context."""
    doc = db.session.get(Document, document_id)
    if doc is None:
        # Document was deleted before the job ran
        return

    job = db.session.execute(
        db.select(DocumentProcessingJob)
        .filter_by(document_id=document_id, status=JobStatus.QUEUED)
    ).scalar_one_or_none()
    if job is None:
        return  # Job was cancelled

    job.status = JobStatus.RUNNING
    job.started_at = datetime.now(timezone.utc)
    doc.status = DocumentStatus.PROCESSING
    db.session.commit()

    try:
        file_path = _resolve_file_path(doc)
        if not file_path.exists():
            raise FileNotFoundError(f'File not found: {file_path}')

        parser = parser_for(doc.file_type)
        pages = parser.parse(file_path)
        chunks = chunker.chunk_pages(
            pages,
            chunk_size=current_app.config.get('CHUNK_SIZE', 500),
            chunk_overlap=current_app.config.get('CHUNK_OVERLAP', 50)
        )

        embedder = current_app.extensions['embedder']
        vector_store = current_app.extensions['vector_store']
        scope_key = (
            'college_wide'
            if doc.scope == DocumentScope.COLLEGE_WIDE
            else f'private_{doc.user_id}'
        )

        # Persist chunks and flush so IDs are populated
        db_chunks = []
        for i, chunk in enumerate(chunks):
            db_chunk = DocumentChunk(
                document_id=doc.id,
                chunk_index=i,
                content=chunk.content,
                embedding_model=embedder.model_name,
                page_number=chunk.page_number,
                metadata_json=json.dumps(chunk.metadata)
            )
            db_chunks.append(db_chunk)

        db.session.add_all(db_chunks)
        db.session.flush()  # Populates db_chunk.id for each object

        # F11: Detect image files with no extractable text (OCR unavailable or blank image)
        if len(db_chunks) == 0 and doc.file_type in ('png', 'jpg', 'jpeg'):
            if not OCR_AVAILABLE:
                error_msg = (
                    'No text extracted. Tesseract OCR may not be installed.'
                )
            else:
                error_msg = 'No text was found in this image.'
            doc.status = DocumentStatus.FAILED
            job.status = JobStatus.FAILED
            job.error_message = error_msg
            job.completed_at = datetime.now(timezone.utc)
            db.session.commit()
            return

        # Embed and add to vector store
        if db_chunks:
            texts = [c.content for c in db_chunks]
            embeddings = embedder.embed(texts)
            meta_entries = [
                {
                    'chunk_db_id': c.id,
                    'document_id': doc.id,
                    'scope': doc.scope.value,
                    'user_id': doc.user_id
                }
                for c in db_chunks
            ]
            vector_store.add_chunks(scope_key, embeddings, meta_entries)

        doc.status = DocumentStatus.READY
        job.status = JobStatus.DONE
        job.completed_at = datetime.now(timezone.utc)
        db.session.commit()
        logger.info('Document %d ingested successfully: %d chunks', document_id, len(db_chunks))

    except Exception as exc:
        db.session.rollback()
        doc = db.session.get(Document, document_id)
        job = db.session.execute(
            db.select(DocumentProcessingJob)
            .filter_by(document_id=document_id)
            .order_by(DocumentProcessingJob.id.desc())
        ).scalar_one_or_none()
        if doc:
            doc.status = DocumentStatus.FAILED
        if job:
            job.status = JobStatus.FAILED
            job.error_message = str(exc)[:500]
            job.completed_at = datetime.now(timezone.utc)
        db.session.commit()
        logger.error('Ingestion failed for doc %d: %s', document_id, exc)
