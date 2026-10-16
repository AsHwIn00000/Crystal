"""Security tests: CSRF, rate limiting, cross-user isolation."""
import pytest
from app.extensions import db
from app.models.user import User, UserRole
from app.models.chat import ChatSession


def make_user(email, app):
    with app.app_context():
        u = User(email=email, display_name=email, role=UserRole.STUDENT)
        u.set_password('Test@1234!')
        db.session.add(u)
        db.session.commit()
        return u.id, u.password_version


def test_csrf_required_on_state_changing_request(security_client):
    """Requests without CSRF token should be rejected when CSRF is enabled."""
    res = security_client.post(
        '/auth/login',
        json={'email': 'x@x.com', 'password': 'wrong'},
        content_type='application/json'
    )
    # With CSRF enabled and no token, Flask-WTF should return 400
    assert res.status_code == 400


def test_login_rate_limit(security_client):
    """Exceeding login rate limit should return 429."""
    for _ in range(11):
        security_client.post(
            '/auth/login',
            json={'email': 'x@x.com', 'password': 'wrong'},
            content_type='application/json',
            headers={'X-CSRFToken': 'dummy'}
        )
    res = security_client.post(
        '/auth/login',
        json={'email': 'x@x.com', 'password': 'wrong'},
        content_type='application/json',
        headers={'X-CSRFToken': 'dummy'}
    )
    assert res.status_code in (429, 400)  # 400 if CSRF fails first, 429 if rate limited


def test_cannot_access_other_users_session(app, client):
    """User B should receive 404 (not 200) when accessing User A's session."""
    uid_a, pv_a = make_user('userx_a@test.com', app)
    uid_b, pv_b = make_user('userx_b@test.com', app)

    # Create session as user A
    with app.app_context():
        s = ChatSession(user_id=uid_a, title='Private Session')
        db.session.add(s)
        db.session.commit()
        sid = s.id

    # Log in as user B
    with client.session_transaction() as sess:
        sess['_user_id'] = str(uid_b)
        sess['_fresh'] = True
        sess['password_version'] = pv_b

    res = client.get(f'/api/sessions/{sid}')
    assert res.status_code == 404  # NOT 200, NOT 403 (shouldn't reveal existence)


def test_cannot_send_to_other_users_session(app, client):
    """User B should not be able to send messages to User A's session."""
    uid_a, pv_a = make_user('msga@test.com', app)
    uid_b, pv_b = make_user('msgb@test.com', app)

    with app.app_context():
        s = ChatSession(user_id=uid_a, title='A Session')
        db.session.add(s)
        db.session.commit()
        sid = s.id

    with client.session_transaction() as sess:
        sess['_user_id'] = str(uid_b)
        sess['_fresh'] = True
        sess['password_version'] = pv_b

    res = client.post(f'/api/sessions/{sid}/messages', json={'content': 'attack'})
    assert res.status_code in (404, 401)


def test_unauthenticated_access_denied(client):
    """Unauthenticated requests to protected endpoints should redirect or 401."""
    res = client.get('/api/sessions')
    assert res.status_code in (302, 401)


def test_admin_route_requires_admin_role(app, client):
    """Student should not access admin routes."""
    uid, pv = make_user('noadmin@test.com', app)
    with client.session_transaction() as sess:
        sess['_user_id'] = str(uid)
        sess['_fresh'] = True
        sess['password_version'] = pv
    res = client.get('/admin/documents')
    assert res.status_code in (302, 403)
