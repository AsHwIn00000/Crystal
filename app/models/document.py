import enum
from datetime import datetime, timezone
from app.extensions import db


class DocumentScope(enum.Enum):
    PRIVATE = 'private'
    COLLEGE_WIDE = 'college_wide'


class DocumentStatus(enum.Enum):
    PENDING = 'pending'
    PROCESSING = 'processing'
    READY = 'ready'
    FAILED = 'failed'


class JobStatus(enum.Enum):
    QUEUED = 'queued'
    RUNNING = 'running'
    DONE = 'done'
    FAILED = 'failed'


class Document(db.Model):
    __tablename__ = 'documents'

    id = db.Column(db.Integer, primary_key=True)
    # user_id is NULL for COLLEGE_WIDE scope documents
    user_id = db.Column(
        db.Integer,
        db.ForeignKey('users.id', ondelete='CASCADE'),
        nullable=True,
        index=True
    )
    filename_original = db.Column(db.String(255), nullable=False)
    filename_stored = db.Column(db.String(64), nullable=False, unique=True)  # uuid4 + ext
    scope = db.Column(db.Enum(DocumentScope), nullable=False, default=DocumentScope.PRIVATE)
    status = db.Column(db.Enum(DocumentStatus), nullable=False, default=DocumentStatus.PENDING)
    file_type = db.Column(db.String(20), nullable=False)
    file_size = db.Column(db.BigInteger, nullable=False)
    created_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )
    updated_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )

    owner = db.relationship('User', back_populates='documents')
    chunks = db.relationship(
        'DocumentChunk', back_populates='document',
        cascade='all, delete-orphan', lazy='dynamic'
    )
    jobs = db.relationship(
        'DocumentProcessingJob', back_populates='document',
        cascade='all, delete-orphan', lazy='dynamic'
    )

    __table_args__ = (
        db.Index('ix_doc_user_scope', 'user_id', 'scope'),
        db.Index('ix_doc_scope_status', 'scope', 'status'),
    )


class DocumentChunk(db.Model):
    __tablename__ = 'document_chunks'

    id = db.Column(db.Integer, primary_key=True)
    document_id = db.Column(
        db.Integer,
        db.ForeignKey('documents.id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )
    chunk_index = db.Column(db.Integer, nullable=False)
    content = db.Column(db.Text, nullable=False)
    embedding_model = db.Column(db.String(100))
    page_number = db.Column(db.Integer)
    metadata_json = db.Column(db.Text)

    document = db.relationship('Document', back_populates='chunks')

    __table_args__ = (
        db.UniqueConstraint('document_id', 'chunk_index', name='uq_chunk_doc_idx'),
    )


class DocumentProcessingJob(db.Model):
    __tablename__ = 'document_processing_jobs'

    id = db.Column(db.Integer, primary_key=True)
    document_id = db.Column(
        db.Integer,
        db.ForeignKey('documents.id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )
    status = db.Column(db.Enum(JobStatus), nullable=False, default=JobStatus.QUEUED)
    error_message = db.Column(db.Text)
    started_at = db.Column(db.DateTime(timezone=True))
    completed_at = db.Column(db.DateTime(timezone=True))

    document = db.relationship('Document', back_populates='jobs')


class OCRUsageEvent(db.Model):
    """Tracks OCR API calls for quota monitoring."""
    __tablename__ = 'ocr_usage_events'

    id              = db.Column(db.Integer, primary_key=True)
    document_id     = db.Column(
        db.Integer,
        db.ForeignKey('documents.id', ondelete='CASCADE'),
        nullable=False
    )
    provider        = db.Column(db.String(50), nullable=False)  # 'unlimited_ocr' | 'tesseract'
    pages_processed = db.Column(db.Integer, nullable=False, default=0)
    success         = db.Column(db.Boolean, nullable=False, default=True)
    error_message   = db.Column(db.Text)
    created_at      = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )
