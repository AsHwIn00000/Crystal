import os
from pathlib import Path
from flask import request, jsonify, current_app, abort, send_from_directory
from flask_login import login_required, current_user
from app.blueprints.documents import documents_bp
from app.extensions import db
from app.models.document import Document, DocumentChunk, DocumentProcessingJob, DocumentScope, DocumentStatus, JobStatus
from app.ingestion.validators import validate_upload, ValidationError
from app.ingestion.job_runner import get_job_runner
from app.ingestion.pipeline import ingest_document


@documents_bp.route('/documents', methods=['GET'])
@login_required
def list_documents():
    page = max(1, request.args.get('page', 1, type=int))
    per_page = min(100, max(1, request.args.get('per_page', 20, type=int)))
    scope_filter = request.args.get('scope')

    query = db.select(Document).order_by(Document.created_at.desc())

    if current_user.role.value == 'admin':
        # Admin sees all documents
        if scope_filter == 'private':
            query = query.where(Document.scope == DocumentScope.PRIVATE)
        elif scope_filter == 'college_wide':
            query = query.where(Document.scope == DocumentScope.COLLEGE_WIDE)
    else:
        # Students see their own private + all college_wide
        if scope_filter == 'private':
            query = query.where(
                Document.scope == DocumentScope.PRIVATE,
                Document.user_id == current_user.id
            )
        elif scope_filter == 'college_wide':
            query = query.where(Document.scope == DocumentScope.COLLEGE_WIDE)
        else:
            query = query.where(
                db.or_(
                    db.and_(Document.scope == DocumentScope.PRIVATE, Document.user_id == current_user.id),
                    Document.scope == DocumentScope.COLLEGE_WIDE
                )
            )

    from sqlalchemy import func
    total = db.session.execute(
        db.select(func.count()).select_from(query.subquery())
    ).scalar()

    offset = (page - 1) * per_page
    docs = db.session.execute(query.offset(offset).limit(per_page)).scalars().all()

    import math
    pages = math.ceil(total / per_page) if total else 1

    return jsonify({
        'documents': [
            {
                'id': d.id,
                'filename_original': d.filename_original,
                'file_type': d.file_type,
                'file_size': d.file_size,
                'scope': d.scope.value,
                'status': d.status.value,
                'created_at': d.created_at.isoformat(),
                'updated_at': d.updated_at.isoformat()
            }
            for d in docs
        ],
        'total': total,
        'page': page,
        'pages': pages
    }), 200


@documents_bp.route('/documents', methods=['POST'])
@login_required
def upload_document():
    """Upload a private document. College-wide uploads go through POST /admin/documents."""
    file = request.files.get('file')
    if not file:
        return jsonify({'error': 'No file provided.'}), 400

    try:
        ext, stored_name, size = validate_upload(file)
    except ValidationError as e:
        return jsonify({'error': str(e)}), 400

    upload_folder = Path(current_app.config['UPLOAD_FOLDER'])
    upload_dir = upload_folder / 'private' / str(current_user.id)
    upload_dir.mkdir(parents=True, exist_ok=True)
    file_path = upload_dir / stored_name

    try:
        file.save(str(file_path))
    except Exception as e:
        current_app.logger.error('File save failed: %s', e)
        return jsonify({'error': 'File upload failed.'}), 500

    try:
        doc = Document(
            user_id=current_user.id,
            filename_original=file.filename,
            filename_stored=stored_name,
            scope=DocumentScope.PRIVATE,
            status=DocumentStatus.PENDING,
            file_type=ext,
            file_size=size
        )
        db.session.add(doc)
        db.session.flush()

        job = DocumentProcessingJob(document_id=doc.id, status=JobStatus.QUEUED)
        db.session.add(job)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        # Remove file if DB save failed
        if file_path.exists():
            file_path.unlink()
        current_app.logger.error('DB save failed after file upload: %s', e)
        return jsonify({'error': 'Failed to save document record.'}), 500

    get_job_runner().submit(ingest_document, doc.id)

    return jsonify({
        'document': {
            'id': doc.id,
            'filename_original': doc.filename_original,
            'status': doc.status.value,
            'file_type': doc.file_type,
            'created_at': doc.created_at.isoformat()
        }
    }), 202


@documents_bp.route('/documents/<int:doc_id>/status', methods=['GET'])
@login_required
def get_document_status(doc_id):
    doc = db.session.get(Document, doc_id)
    if doc is None:
        abort(404)
    # Authorization: own private doc OR college_wide
    if doc.scope == DocumentScope.PRIVATE and doc.user_id != current_user.id:
        if current_user.role.value != 'admin':
            abort(404)

    # Get most recent job
    job = db.session.execute(
        db.select(DocumentProcessingJob)
        .where(DocumentProcessingJob.document_id == doc_id)
        .order_by(DocumentProcessingJob.id.desc())
    ).scalar_one_or_none()

    job_data = None
    if job:
        job_data = {
            'status': job.status.value,
            'error_message': job.error_message,
            'started_at': job.started_at.isoformat() if job.started_at else None,
            'completed_at': job.completed_at.isoformat() if job.completed_at else None
        }

    return jsonify({
        'status': doc.status.value,
        'job': job_data
    }), 200


@documents_bp.route('/documents/<int:doc_id>', methods=['DELETE'])
@login_required
def delete_document(doc_id):
    doc = db.session.get(Document, doc_id)
    if doc is None:
        abort(404)
    # Authorization: own private doc only (admin deletes college-wide via /admin/documents)
    if doc.scope == DocumentScope.PRIVATE and doc.user_id != current_user.id:
        abort(404)
    if doc.scope == DocumentScope.COLLEGE_WIDE and current_user.role.value != 'admin':
        abort(403)

    # Cancel any running/queued jobs
    active_jobs = db.session.execute(
        db.select(DocumentProcessingJob)
        .where(
            DocumentProcessingJob.document_id == doc_id,
            DocumentProcessingJob.status.in_([JobStatus.RUNNING, JobStatus.QUEUED])
        )
    ).scalars().all()
    for job in active_jobs:
        job.status = JobStatus.FAILED
        job.error_message = 'Cancelled by user deletion.'

    # Remove physical file
    upload_folder = Path(current_app.config['UPLOAD_FOLDER'])
    if doc.scope == DocumentScope.PRIVATE:
        file_path = upload_folder / 'private' / str(doc.user_id) / doc.filename_stored
    else:
        file_path = upload_folder / 'college_wide' / doc.filename_stored

    try:
        if file_path.exists():
            file_path.unlink()
    except FileNotFoundError:
        current_app.logger.warning('File already gone on delete: %s', file_path)

    db.session.delete(doc)
    db.session.commit()

    return '', 204
