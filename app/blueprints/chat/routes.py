from flask import request, jsonify, current_app, abort
from flask_login import login_required, current_user
from sqlalchemy import func
from app.blueprints.chat import chat_bp
from app.extensions import db
from app.models.chat import ChatSession, ChatMessage, MessageRole, SavedPrompt
from app.models.document import Document, DocumentScope, DocumentStatus
from app.models.feedback import Feedback
from app.ai.base_provider import AIRateLimitError, AITimeoutError, AIAuthError, AIProviderError
from app.ai.prompt_builder import PromptBuilder
from app.rag.retriever import HybridRetriever


# ── Sessions ─────────────────────────────────────────────────────────────────

@chat_bp.route('/sessions', methods=['POST'])
@login_required
def create_session():
    data = request.get_json(silent=True) or {}
    title = str(data.get('title', 'New Conversation'))[:200].strip() or 'New Conversation'

    session = ChatSession(user_id=current_user.id, title=title)
    db.session.add(session)
    db.session.commit()

    return jsonify({
        'session': {
            'id': session.id,
            'title': session.title,
            'created_at': session.created_at.isoformat(),
            'updated_at': session.updated_at.isoformat(),
            'message_count': 0
        }
    }), 201


@chat_bp.route('/sessions', methods=['GET'])
@login_required
def list_sessions():
    page = max(1, request.args.get('page', 1, type=int))
    per_page = min(100, max(1, request.args.get('per_page', 20, type=int)))

    # Subquery for message count per session
    msg_count_sq = (
        db.select(
            ChatMessage.session_id,
            func.count(ChatMessage.id).label('message_count')
        )
        .group_by(ChatMessage.session_id)
        .subquery()
    )

    query = (
        db.select(ChatSession, func.coalesce(msg_count_sq.c.message_count, 0).label('message_count'))
        .outerjoin(msg_count_sq, ChatSession.id == msg_count_sq.c.session_id)
        .where(ChatSession.user_id == current_user.id)
        .order_by(ChatSession.updated_at.desc())
    )

    total = db.session.execute(
        db.select(func.count()).select_from(
            db.select(ChatSession.id).where(ChatSession.user_id == current_user.id).subquery()
        )
    ).scalar()

    offset = (page - 1) * per_page
    rows = db.session.execute(query.offset(offset).limit(per_page)).all()

    import math
    pages = math.ceil(total / per_page) if total else 1

    sessions_data = []
    for row in rows:
        s = row[0]
        mc = row[1]
        sessions_data.append({
            'id': s.id,
            'title': s.title,
            'created_at': s.created_at.isoformat(),
            'updated_at': s.updated_at.isoformat(),
            'message_count': mc
        })

    return jsonify({
        'sessions': sessions_data,
        'total': total,
        'page': page,
        'pages': pages
    }), 200


@chat_bp.route('/sessions/<int:session_id>', methods=['GET'])
@login_required
def get_session(session_id):
    session = db.session.execute(
        db.select(ChatSession).filter_by(id=session_id, user_id=current_user.id)
    ).scalar_one_or_none()
    if session is None:
        abort(404)

    return jsonify({
        'session': {
            'id': session.id,
            'title': session.title,
            'created_at': session.created_at.isoformat(),
            'updated_at': session.updated_at.isoformat()
        }
    }), 200


@chat_bp.route('/sessions/<int:session_id>', methods=['PUT'])
@login_required
def rename_session(session_id):
    session = db.session.execute(
        db.select(ChatSession).filter_by(id=session_id, user_id=current_user.id)
    ).scalar_one_or_none()
    if session is None:
        abort(404)

    data = request.get_json(silent=True) or {}
    title = str(data.get('title', '')).strip()[:200]
    if not title:
        return jsonify({'error': 'Title cannot be empty.'}), 400

    session.title = title
    db.session.commit()

    return jsonify({
        'session': {
            'id': session.id,
            'title': session.title
        }
    }), 200


@chat_bp.route('/sessions/<int:session_id>', methods=['DELETE'])
@login_required
def delete_session(session_id):
    session = db.session.execute(
        db.select(ChatSession).filter_by(id=session_id, user_id=current_user.id)
    ).scalar_one_or_none()
    if session is None:
        abort(404)

    db.session.delete(session)
    db.session.commit()

    return '', 204


# ── Messages ──────────────────────────────────────────────────────────────────

@chat_bp.route('/sessions/<int:session_id>/messages', methods=['GET'])
@login_required
def get_messages(session_id):
    session = db.session.execute(
        db.select(ChatSession).filter_by(id=session_id, user_id=current_user.id)
    ).scalar_one_or_none()
    if session is None:
        abort(404)

    page = max(1, request.args.get('page', 1, type=int))
    per_page = min(100, max(1, request.args.get('per_page', 50, type=int)))

    total = db.session.execute(
        db.select(func.count(ChatMessage.id)).where(ChatMessage.session_id == session_id)
    ).scalar()

    offset = (page - 1) * per_page
    messages = db.session.execute(
        db.select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at.asc())
        .offset(offset)
        .limit(per_page)
    ).scalars().all()

    import math
    pages = math.ceil(total / per_page) if total else 1

    return jsonify({
        'messages': [
            {
                'id': m.id,
                'role': m.role.value,
                'content': m.content,
                'sources': m.sources,
                'attachments': m.attachments,
                'created_at': m.created_at.isoformat()
            }
            for m in messages
        ],
        'total': total,
        'page': page,
        'pages': pages
    }), 200


@chat_bp.route('/sessions/<int:session_id>/messages', methods=['POST'])
@login_required
def send_message(session_id):
    # 1. Verify session ownership
    session = db.session.get(ChatSession, session_id)
    if not session or session.user_id != current_user.id:
        return jsonify({'error': 'Not found'}), 404

    data = request.get_json(silent=True) or {}
    user_text = str(data.get('content', '')).strip()[:4000]  # bound input
    document_ids = data.get('document_ids', [])
    attachments = data.get('attachments', [])

    if not user_text and not attachments:
        return jsonify({'error': 'Message cannot be empty'}), 400

    if not user_text and attachments:
        user_text = f"Uploaded study file: {attachments[0].get('filename', 'document')}"

    # If no document_ids explicitly passed, inherit from this chat session's uploaded attachments
    if not document_ids:
        prev_attachments = db.session.execute(
            db.select(ChatMessage.attachments_json)
            .filter_by(session_id=session_id)
            .where(ChatMessage.attachments_json.isnot(None))
            .order_by(ChatMessage.created_at.desc())
        ).scalars().all()
        for att_str in prev_attachments:
            try:
                atts = json.loads(att_str) if isinstance(att_str, str) else (att_str or [])
                for a in atts:
                    if isinstance(a, dict) and a.get('doc_id') and a['doc_id'] not in document_ids:
                        document_ids.append(a['doc_id'])
            except Exception:
                pass

    # Validate document_ids ownership and wait briefly if ingestion is still running
    if document_ids:
        import time
        for doc_id in document_ids:
            doc = db.session.get(Document, doc_id)
            if doc is None:
                abort(404)
            if doc.scope == DocumentScope.PRIVATE and doc.user_id != current_user.id:
                abort(403)
            # Wait up to 8 seconds if doc is still processing
            start_wait = time.time()
            while doc.status in (DocumentStatus.PENDING, DocumentStatus.PROCESSING) and (time.time() - start_wait) < 8.0:
                time.sleep(0.5)
                db.session.expire(doc)
                doc = db.session.get(Document, doc_id)

    # 2. Persist user message
    user_msg = ChatMessage(
        session_id=session_id,
        user_id=current_user.id,
        role=MessageRole.USER,
        content=user_text
    )
    if attachments:
        user_msg.attachments = attachments
    db.session.add(user_msg)
    db.session.commit()  # Persist user message immediately

    # 3. Retrieve relevant chunks (scope-filtered)
    try:
        retriever = HybridRetriever(current_app._get_current_object())
        chunks = retriever.retrieve(
            query=user_text,
            user_id=current_user.id,
            document_ids=document_ids if document_ids else None
        )
    except Exception as e:
        current_app.logger.warning('RAG retrieval failed: %s', e)
        chunks = []

    # 4. Build sources_list from retrieved chunks
    sources_list = [
        {
            'doc_id': c.document_id,
            'chunk_id': c.chunk_db_id,
            'title': c.doc_title,
            'page': c.page_number
        }
        for c in chunks
    ]

    # 5. Get recent conversation history (last 10 messages)
    recent = db.session.execute(
        db.select(ChatMessage)
        .filter_by(session_id=session_id)
        .order_by(ChatMessage.created_at.desc())
        .limit(10)
    ).scalars().all()
    recent.reverse()

    # 6. Build prompt with injection defenses
    prompt_builder = PromptBuilder()
    messages = prompt_builder.build(user_text, chunks, recent)

    # 7. Call AI provider
    provider = current_app.extensions['ai_provider']
    try:
        ai_response = provider.chat(messages)
        answer = ai_response.content
    except AIRateLimitError:
        answer = 'The AI service is busy. Please try again in a moment.'
        sources_list = []
    except (AITimeoutError, AIProviderError) as exc:
        current_app.logger.error('AI provider error: %s — %s', type(exc).__name__, exc)
        answer = 'Unable to reach the AI service. Please try again.'
        sources_list = []
    except AIAuthError as exc:
        current_app.logger.critical('AIAuthError — check GROQ_API_KEY: %s', exc)
        answer = 'An internal error occurred.'
        sources_list = []
    except Exception as exc:
        current_app.logger.error('Unexpected error in send_message: %s — %s', type(exc).__name__, exc)
        answer = 'An unexpected error occurred. Please try again.'
        sources_list = []

    # 8. Persist assistant message with sources
    asst_msg = ChatMessage(
        session_id=session_id,
        user_id=current_user.id,
        role=MessageRole.ASSISTANT,
        content=answer
    )
    asst_msg.sources = sources_list
    db.session.add(asst_msg)

    # 9. Update session title if first message
    if session.title == 'New Conversation':
        session.title = user_text[:80]

    db.session.commit()

    return jsonify({
        'message': {
            'id': asst_msg.id,
            'role': 'assistant',
            'content': answer,
            'sources': sources_list,
            'created_at': asst_msg.created_at.isoformat()
        }
    }), 200


# ── Feedback ──────────────────────────────────────────────────────────────────

@chat_bp.route('/messages/<int:message_id>/feedback', methods=['POST'])
@login_required
def submit_feedback(message_id):
    message = db.session.get(ChatMessage, message_id)
    # Use 404 (not 403) to avoid confirming the message exists
    if message is None or message.user_id != current_user.id:
        abort(404)

    data = request.get_json(silent=True) or {}
    rating = data.get('rating')
    comment = str(data.get('comment', '') or '').strip()[:1000]

    # Validate rating before DB write (avoids CheckConstraint 500)
    if rating is None or not isinstance(rating, int) or rating not in range(1, 6):
        return jsonify({'error': 'Rating must be an integer between 1 and 5.'}), 400

    # Check for existing feedback
    existing = db.session.execute(
        db.select(Feedback).filter_by(message_id=message_id, user_id=current_user.id)
    ).scalar_one_or_none()
    if existing:
        return jsonify({'error': 'Feedback already submitted for this message.'}), 409

    feedback = Feedback(
        message_id=message_id,
        user_id=current_user.id,
        rating=rating,
        comment=comment or None
    )
    db.session.add(feedback)
    db.session.commit()

    return jsonify({
        'feedback': {
            'id': feedback.id,
            'message_id': feedback.message_id,
            'rating': feedback.rating,
            'comment': feedback.comment,
            'created_at': feedback.created_at.isoformat()
        }
    }), 201


# ── Saved Prompts ─────────────────────────────────────────────────────────────

@chat_bp.route('/prompts', methods=['GET'])
@login_required
def list_prompts():
    prompts = db.session.execute(
        db.select(SavedPrompt)
        .where(db.or_(SavedPrompt.user_id == current_user.id, SavedPrompt.user_id.is_(None)))
        .order_by(SavedPrompt.id.asc())
    ).scalars().all()
    return jsonify({
        'prompts': [
            {
                'id': p.id,
                'title': p.title,
                'prompt_text': p.prompt_text,
                'category': p.category
            }
            for p in prompts
        ]
    }), 200


@chat_bp.route('/prompts', methods=['POST'])
@login_required
def create_prompt():
    data = request.get_json(silent=True) or {}
    title = str(data.get('title', '')).strip()[:120]
    prompt_text = str(data.get('prompt_text', '')).strip()[:2000]
    category = str(data.get('category', 'Study')).strip()[:50]
    if not title or not prompt_text:
        return jsonify({'error': 'Title and prompt_text are required.'}), 400

    prompt = SavedPrompt(
        user_id=current_user.id,
        title=title,
        prompt_text=prompt_text,
        category=category
    )
    db.session.add(prompt)
    db.session.commit()
    return jsonify({
        'prompt': {
            'id': prompt.id,
            'title': prompt.title,
            'prompt_text': prompt.prompt_text,
            'category': prompt.category
        }
    }), 201

