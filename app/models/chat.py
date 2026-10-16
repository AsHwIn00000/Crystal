import enum
import json
from datetime import datetime, timezone
from app.extensions import db


class MessageRole(enum.Enum):
    USER = 'user'
    ASSISTANT = 'assistant'
    SYSTEM = 'system'


class ChatSession(db.Model):
    __tablename__ = 'chat_sessions'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey('users.id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )
    title = db.Column(db.String(200), nullable=False, default='New Conversation')
    created_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )
    updated_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )

    user = db.relationship('User', back_populates='sessions')
    messages = db.relationship(
        'ChatMessage', back_populates='session',
        cascade='all, delete-orphan',
        order_by='ChatMessage.created_at',
        lazy='dynamic'
    )

    __table_args__ = (
        db.Index('ix_session_user_updated', 'user_id', 'updated_at'),
    )


class ChatMessage(db.Model):
    __tablename__ = 'chat_messages'

    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(
        db.Integer,
        db.ForeignKey('chat_sessions.id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )
    user_id = db.Column(
        db.Integer,
        db.ForeignKey('users.id', ondelete='CASCADE'),
        nullable=False
    )
    role = db.Column(db.Enum(MessageRole), nullable=False)
    content = db.Column(db.Text, nullable=False)
    sources_json = db.Column(db.Text)  # JSON array of {doc_id, chunk_id, title, page}
    attachments_json = db.Column(db.Text, nullable=True)  # JSON array of {doc_id, filename, file_type, file_size}
    created_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )

    session = db.relationship('ChatSession', back_populates='messages')

    @property
    def sources(self):
        return json.loads(self.sources_json) if self.sources_json else []

    @sources.setter
    def sources(self, value: list):
        self.sources_json = json.dumps(value)

    @property
    def attachments(self):
        return json.loads(self.attachments_json) if self.attachments_json else []

    @attachments.setter
    def attachments(self, value: list):
        self.attachments_json = json.dumps(value)


class SavedPrompt(db.Model):
    __tablename__ = 'saved_prompts'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey('users.id', ondelete='CASCADE'),
        nullable=True,
        index=True
    )
    title = db.Column(db.String(120), nullable=False)
    prompt_text = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(50), default='General')
    created_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )

    user = db.relationship('User', backref=db.backref('saved_prompts', lazy='dynamic'))
