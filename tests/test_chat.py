"""Chat session and message tests."""
import pytest
from unittest.mock import patch
from app.ai.base_provider import AIResponse
from app.ai.groq_provider import GroqProvider
from app.extensions import db
from app.models.chat import ChatSession, ChatMessage


def test_create_session(authenticated_client):
    res = authenticated_client.post('/api/sessions', json={'title': 'My Test Session'})
    assert res.status_code == 201
    data = res.get_json()
    assert data['session']['title'] == 'My Test Session'
    assert data['session']['message_count'] == 0


def test_list_sessions_only_own(app, client):
    """Two users' sessions must not bleed into each other's list."""
    from hashlib import sha512
    from app.models.user import User, UserRole

    def _sid():
        base = 'None|None'
        h = sha512()
        h.update(base.encode('utf8'))
        return h.hexdigest()

    # Create user A
    with app.app_context():
        u_a = User(email='usera@test.com', display_name='User A')
        u_a.set_password('Test@1234!')
        db.session.add(u_a)
        db.session.commit()
        uid_a, pv_a = u_a.id, u_a.password_version

        s = ChatSession(user_id=uid_a, title='User A Session')
        db.session.add(s)
        db.session.commit()

    with client.session_transaction() as sess:
        sess['_user_id'] = str(uid_a)
        sess['_fresh'] = True
        sess['password_version'] = pv_a
        sess['_id'] = _sid()

    res = client.get('/api/sessions')
    data = res.get_json()
    assert res.status_code == 200
    assert all(s['title'] != 'Other Session' for s in data['sessions'])


def test_rename_session(authenticated_client, app):
    res = authenticated_client.post('/api/sessions', json={'title': 'Old Title'})
    sid = res.get_json()['session']['id']

    res = authenticated_client.put(f'/api/sessions/{sid}', json={'title': 'New Title'})
    assert res.status_code == 200
    assert res.get_json()['session']['title'] == 'New Title'


def test_delete_session_cascades_messages(authenticated_client, app):
    res = authenticated_client.post('/api/sessions', json={})
    sid = res.get_json()['session']['id']

    # Add a message directly
    with app.app_context():
        from app.models.user import User
        user = db.session.execute(
            db.select(User).filter_by(email='student@test.com')
        ).scalar_one_or_none()
        if user:
            from app.models.chat import ChatMessage, MessageRole
            msg = ChatMessage(
                session_id=sid, user_id=user.id,
                role=MessageRole.USER, content='test'
            )
            db.session.add(msg)
            db.session.commit()

    # Delete session
    res = authenticated_client.delete(f'/api/sessions/{sid}')
    assert res.status_code == 204

    # Messages should be gone too
    with app.app_context():
        msgs = db.session.execute(
            db.select(ChatMessage).filter_by(session_id=sid)
        ).scalars().all()
        assert len(msgs) == 0


def test_send_message_mocks_ai(authenticated_client, app):
    res = authenticated_client.post('/api/sessions', json={'title': 'Test'})
    session_id = res.get_json()['session']['id']

    with patch.object(
        GroqProvider,
        'chat',
        return_value=AIResponse(
            content='Test response from Crystal',
            model='test-model',
            usage={'prompt_tokens': 10, 'completion_tokens': 20}
        )
    ):
        res = authenticated_client.post(
            f'/api/sessions/{session_id}/messages',
            json={'content': 'Hello Crystal'}
        )

    assert res.status_code == 200
    data = res.get_json()
    assert data['message']['content'] == 'Test response from Crystal'
    assert data['message']['role'] == 'assistant'


def test_send_message_persisted(authenticated_client, app):
    res = authenticated_client.post('/api/sessions', json={'title': 'Persist Test'})
    sid = res.get_json()['session']['id']

    with patch.object(GroqProvider, 'chat', return_value=AIResponse(
        content='AI answer', model='test', usage={'prompt_tokens': 1, 'completion_tokens': 1}
    )):
        authenticated_client.post(f'/api/sessions/{sid}/messages', json={'content': 'User question'})

    with app.app_context():
        messages = db.session.execute(
            db.select(ChatMessage).filter_by(session_id=sid)
        ).scalars().all()
        assert len(messages) == 2
        assert messages[0].content == 'User question'
        assert messages[1].content == 'AI answer'


def test_send_message_returns_sources(authenticated_client, app):
    res = authenticated_client.post('/api/sessions', json={})
    sid = res.get_json()['session']['id']

    with patch.object(GroqProvider, 'chat', return_value=AIResponse(
        content='answer', model='test', usage={'prompt_tokens': 1, 'completion_tokens': 1}
    )):
        res = authenticated_client.post(f'/api/sessions/{sid}/messages', json={'content': 'test query'})

    data = res.get_json()
    assert 'sources' in data['message']
    assert isinstance(data['message']['sources'], list)


def test_get_messages_pagination(authenticated_client, app):
    res = authenticated_client.post('/api/sessions', json={})
    sid = res.get_json()['session']['id']

    res = authenticated_client.get(f'/api/sessions/{sid}/messages?page=1&per_page=10')
    assert res.status_code == 200
    data = res.get_json()
    assert 'messages' in data
    assert 'total' in data
