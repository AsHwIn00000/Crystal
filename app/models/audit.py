import json
from datetime import datetime, timezone
from app.extensions import db


class AuditEvent(db.Model):
    __tablename__ = 'audit_events'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey('users.id', ondelete='SET NULL'),
        nullable=True
    )
    event_type = db.Column(db.String(50), nullable=False, index=True)
    resource_type = db.Column(db.String(50))
    resource_id = db.Column(db.Integer)
    ip_address = db.Column(db.String(45))
    created_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        index=True
    )
    details_json = db.Column(db.Text)

    user = db.relationship('User', back_populates='audit_events')

    @staticmethod
    def log(event_type, resource_type=None, resource_id=None,
            user_id=None, ip_address=None, details=None):
        """Log an audit event. Caller is responsible for db.session.commit()."""
        from app.extensions import db as _db
        event = AuditEvent(
            event_type=event_type,
            resource_type=resource_type,
            resource_id=resource_id,
            user_id=user_id,
            ip_address=ip_address,
            details_json=json.dumps(details) if details else None
        )
        _db.session.add(event)
        # NEVER log raw passwords, API keys, full message content, or file bytes
