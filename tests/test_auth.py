"""Auth tests."""
import pytest
from app.extensions import db
from app.models.user import User, UserRole


def test_register_success(client, app):
    res = client.post('/auth/register', json={
        'email': 'new@test.com',
        'password': 'Test@1234!',
        'confirm_password': 'Test@1234!',
        'display_name': 'New User'
    })
    assert res.status_code == 201
    data = res.get_json()
    assert data['user']['email'] == 'new@test.com'


def test_register_duplicate_email_generic_error(client, app):
    """Registration of existing email must not reveal 'email already exists'."""
    # Register first time
    client.post('/auth/register', json={
        'email': 'dup@test.com', 'password': 'Test@1234!',
        'confirm_password': 'Test@1234!', 'display_name': 'First'
    })
    # Register again with same email
    res = client.post('/auth/register', json={
        'email': 'dup@test.com', 'password': 'Test@1234!',
        'confirm_password': 'Test@1234!', 'display_name': 'Second'
    })
    assert res.status_code == 400
    data = res.get_json()
    # Must NOT say "email already exists" or similar
    assert 'already' not in data.get('error', '').lower()
    assert 'exist' not in data.get('error', '').lower()


def test_register_weak_password(client):
    res = client.post('/auth/register', json={
        'email': 'weak@test.com', 'password': 'short',
        'confirm_password': 'short', 'display_name': 'Weak'
    })
    assert res.status_code == 400


def test_login_wrong_password_generic_error(client, app):
    # Create user
    with app.app_context():
        u = User(email='login@test.com', display_name='Login Test')
        u.set_password('Test@1234!')
        db.session.add(u)
        db.session.commit()

    res = client.post('/auth/login', json={
        'email': 'login@test.com', 'password': 'WrongPass!'
    })
    assert res.status_code == 401
    data = res.get_json()
    assert 'Invalid' in data.get('error', '')


def test_login_inactive_user_generic_error(client, app):
    with app.app_context():
        u = User(email='inactive@test.com', display_name='Inactive', is_active=False)
        u.set_password('Test@1234!')
        db.session.add(u)
        db.session.commit()

    res = client.post('/auth/login', json={
        'email': 'inactive@test.com', 'password': 'Test@1234!'
    })
    assert res.status_code == 401


def test_logout_invalidates_session(client, app, authenticated_client):
    # Verify we are logged in
    res = authenticated_client.get('/auth/me')
    assert res.status_code == 200

    # Logout
    res = authenticated_client.post('/auth/logout')
    assert res.status_code == 200

    # Should now be unauthorized
    res = authenticated_client.get('/auth/me')
    assert res.status_code in (401, 302)


def test_get_me_authenticated(authenticated_client):
    res = authenticated_client.get('/auth/me')
    assert res.status_code == 200
    data = res.get_json()
    assert 'user' in data
    assert data['user']['email'] == 'student@test.com'


def test_password_change_requires_current_password(authenticated_client):
    res = authenticated_client.put('/auth/password', json={
        'current_password': 'WrongPassword!',
        'new_password': 'NewPass@123!',
        'confirm_new_password': 'NewPass@123!'
    })
    assert res.status_code == 400


def test_update_profile(authenticated_client):
    res = authenticated_client.put('/auth/profile', json={'display_name': 'Updated Name'})
    assert res.status_code == 200
    data = res.get_json()
    assert data['user']['display_name'] == 'Updated Name'
