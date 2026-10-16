from datetime import datetime, timezone
from app.extensions import db


class Feedback(db.Model):
    __tablename__ = 'feedback'

    id = db.Column(db.Integer, primary_key=True)
    message_id = db.Column(
        db.Integer,
        db.ForeignKey('chat_messages.id', ondelete='CASCADE'),
        nullable=False
    )
    user_id = db.Column(
        db.Integer,
        db.ForeignKey('users.id', ondelete='CASCADE'),
        nullable=False
    )
    rating = db.Column(db.SmallInteger, nullable=False)  # 1–5, validated server-side
    comment = db.Column(db.Text)
    created_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )

    user = db.relationship('User', back_populates='feedbacks')
    message = db.relationship('ChatMessage')

    __table_args__ = (
        db.UniqueConstraint('message_id', 'user_id', name='uq_feedback_msg_user'),
        db.CheckConstraint('rating BETWEEN 1 AND 5', name='ck_feedback_rating'),
    )
