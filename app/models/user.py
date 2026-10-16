import enum
from datetime import datetime, timezone
from app.extensions import db
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash


class UserRole(enum.Enum):
    STUDENT = 'student'
    ADMIN = 'admin'


class User(UserMixin, db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    password_version = db.Column(db.Integer, nullable=False, default=0)
    role = db.Column(db.Enum(UserRole), nullable=False, default=UserRole.STUDENT)
    display_name = db.Column(db.String(100))
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )
    updated_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    sessions = db.relationship(
        'ChatSession', back_populates='user',
        cascade='all, delete-orphan', lazy='dynamic'
    )
    documents = db.relationship(
        'Document', back_populates='owner',
        cascade='all, delete-orphan', lazy='dynamic'
    )
    feedbacks = db.relationship('Feedback', back_populates='user', lazy='dynamic')
    audit_events = db.relationship('AuditEvent', back_populates='user', lazy='dynamic')

    def set_password(self, password: str) -> None:
        """Hash and store the password. NEVER stores plaintext."""
        self.password_hash = generate_password_hash(
            password, method='pbkdf2:sha256:600000'
        )
        self.password_version = (self.password_version or 0) + 1

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    @staticmethod
    def normalize_email(email: str) -> str:
        return email.strip().lower()
