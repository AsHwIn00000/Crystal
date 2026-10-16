import math
from pathlib import Path
from flask import request, jsonify, current_app, abort, render_template
from flask_login import login_required
from sqlalchemy import func
from app.blueprints.admin import admin_bp
from app.extensions import db
from app.models.user import User
from app.models.document import Document, DocumentProcessingJob, DocumentScope, DocumentStatus, JobStatus
from app.models.audit import AuditEvent
from app.models.chat import ChatSession
from app.utils.security import admin_required
from app.ingestion.validators import validate_upload, ValidationError
from app.ingestion.job_runner import get_job_runner
from app.ingestion.pipeline import ingest_document


@admin_bp.route('/')
@login_required
@admin_required
def admin_dashboard():
    return render_template('admin/dashboard.html')


@admin_bp.route('/stats', methods=['GET'])
@login_required
@admin_required
def get_stats():
    from datetime import datetime, timezone, timedelta
    today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    total_users = db.session.execute(db.select(func.count(User.id))).scalar()
    active_sessions_today = db.session.execute(
        db.select(func.count(ChatSession.id))
        .where(ChatSession.updated_at >= today)
    ).scalar()
    private_docs = db.session.execute(
        db.select(func.count(Document.id))
        .where(Document.scope == DocumentScope.PRIVATE)
    ).scalar()
    college_docs = db.session.execute(
        db.select(func.count(Document.id))
        .where(Document.scope == DocumentScope.COLLEGE_WIDE)
    ).scalar()
    failed_docs = db.session.execute(
        db.select(func.count(Document.id))
        .where(Document.status == DocumentStatus.FAILED)
    ).scalar()

    return jsonify({
        'total_users': total_users,
        'active_sessions_today': active_sessions_today,
        'private_docs': private_docs,
        'college_docs': college_docs,
        'failed_docs': failed_docs
    }), 200


@admin_bp.route('/documents', methods=['GET'])
@login_required
@admin_required
def list_college_docs():
    page = max(1, request.args.get('page', 1, type=int))
    per_page = min(100, max(1, request.args.get('per_page', 20, type=int)))

    query = (
        db.select(Document)
        .where(Document.scope == DocumentScope.COLLEGE_WIDE)
        .order_by(Document.created_at.desc())
    )
    total = db.session.execute(
        db.select(func.count()).select_from(query.subquery())
    ).scalar()

    offset = (page - 1) * per_page
    docs = db.session.execute(query.offset(offset).limit(per_page)).scalars().all()
    pages = math.ceil(total / per_page) if total else 1

    return jsonify({
        'documents': [
            {
                'id': d.id,
                'filename_original': d.filename_original,
                'file_type': d.file_type,
                'file_size': d.file_size,
                'status': d.status.value,
                'created_at': d.created_at.isoformat()
            }
            for d in docs
        ],
        'total': total,
        'page': page,
        'pages': pages
    }), 200


@admin_bp.route('/documents', methods=['POST'])
@login_required
@admin_required
def upload_college_doc():
    """Upload a college-wide document (admin only)."""
    file = request.files.get('file')
    if not file:
        return jsonify({'error': 'No file provided.'}), 400

    try:
        ext, stored_name, size = validate_upload(file)
    except ValidationError as e:
        return jsonify({'error': str(e)}), 400

    upload_folder = Path(current_app.config['UPLOAD_FOLDER'])
    upload_dir = upload_folder / 'college_wide'
    upload_dir.mkdir(parents=True, exist_ok=True)
    file_path = upload_dir / stored_name

    try:
        file.save(str(file_path))
    except Exception as e:
        current_app.logger.error('College-wide file save failed: %s', e)
        return jsonify({'error': 'File upload failed.'}), 500

    try:
        doc = Document(
            user_id=None,  # NULL sentinel for college-wide docs
            filename_original=file.filename,
            filename_stored=stored_name,
            scope=DocumentScope.COLLEGE_WIDE,
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
        if file_path.exists():
            file_path.unlink()
        current_app.logger.error('DB save failed after college-wide upload: %s', e)
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


@admin_bp.route('/documents/<int:doc_id>/status', methods=['GET'])
@login_required
@admin_required
def doc_ingestion_status(doc_id):
    doc = db.session.get(Document, doc_id)
    if doc is None or doc.scope != DocumentScope.COLLEGE_WIDE:
        abort(404)

    job = db.session.execute(
        db.select(DocumentProcessingJob)
        .where(DocumentProcessingJob.document_id == doc_id)
        .order_by(DocumentProcessingJob.id.desc())
    ).scalar_one_or_none()

    return jsonify({
        'status': doc.status.value,
        'job': {
            'status': job.status.value,
            'error_message': job.error_message,
            'started_at': job.started_at.isoformat() if job and job.started_at else None,
            'completed_at': job.completed_at.isoformat() if job and job.completed_at else None
        } if job else None
    }), 200


@admin_bp.route('/documents/<int:doc_id>', methods=['DELETE'])
@login_required
@admin_required
def delete_college_doc(doc_id):
    doc = db.session.get(Document, doc_id)
    if doc is None or doc.scope != DocumentScope.COLLEGE_WIDE:
        abort(404)

    # Cancel active jobs
    active_jobs = db.session.execute(
        db.select(DocumentProcessingJob)
        .where(
            DocumentProcessingJob.document_id == doc_id,
            DocumentProcessingJob.status.in_([JobStatus.RUNNING, JobStatus.QUEUED])
        )
    ).scalars().all()
    for job in active_jobs:
        job.status = JobStatus.FAILED
        job.error_message = 'Cancelled by admin deletion.'

    # Remove file
    upload_folder = Path(current_app.config['UPLOAD_FOLDER'])
    file_path = upload_folder / 'college_wide' / doc.filename_stored
    try:
        if file_path.exists():
            file_path.unlink()
    except FileNotFoundError:
        current_app.logger.warning('File already gone: %s', file_path)

    db.session.delete(doc)
    db.session.commit()

    return '', 204


@admin_bp.route('/users', methods=['GET'])
@login_required
@admin_required
def list_users():
    page = max(1, request.args.get('page', 1, type=int))
    per_page = min(100, max(1, request.args.get('per_page', 20, type=int)))

    query = db.select(User).order_by(User.created_at.desc())
    total = db.session.execute(
        db.select(func.count()).select_from(query.subquery())
    ).scalar()
    offset = (page - 1) * per_page
    users = db.session.execute(query.offset(offset).limit(per_page)).scalars().all()
    pages = math.ceil(total / per_page) if total else 1

    return jsonify({
        'users': [
            {
                'id': u.id,
                'email': u.email,
                'display_name': u.display_name,
                'role': u.role.value,
                'is_active': u.is_active,
                'created_at': u.created_at.isoformat()
            }
            for u in users
        ],
        'total': total,
        'page': page,
        'pages': pages
    }), 200


@admin_bp.route('/users/<int:user_id>/toggle-active', methods=['PUT'])
@login_required
@admin_required
def toggle_user_active(user_id):
    user = db.session.get(User, user_id)
    if user is None:
        abort(404)

    user.is_active = not user.is_active
    db.session.commit()

    AuditEvent.log(
        event_type='user_active_toggled',
        resource_type='user',
        resource_id=user_id,
        user_id=user_id,
        details={'is_active': user.is_active}
    )
    db.session.commit()

    return jsonify({
        'user': {
            'id': user.id,
            'is_active': user.is_active
        }
    }), 200


@admin_bp.route('/audit', methods=['GET'])
@login_required
@admin_required
def list_audit_events():
    page = max(1, request.args.get('page', 1, type=int))
    per_page = min(100, max(1, request.args.get('per_page', 50, type=int)))

    query = db.select(AuditEvent).order_by(AuditEvent.created_at.desc())
    total = db.session.execute(
        db.select(func.count()).select_from(query.subquery())
    ).scalar()
    offset = (page - 1) * per_page
    events = db.session.execute(query.offset(offset).limit(per_page)).scalars().all()
    pages = math.ceil(total / per_page) if total else 1

    return jsonify({
        'events': [
            {
                'id': e.id,
                'event_type': e.event_type,
                'user_id': e.user_id,
                'resource_type': e.resource_type,
                'resource_id': e.resource_id,
                'ip_address': e.ip_address,
                'created_at': e.created_at.isoformat()
            }
            for e in events
        ],
        'total': total,
        'page': page,
        'pages': pages
    }), 200
