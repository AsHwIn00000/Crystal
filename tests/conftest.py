import pytest
from app import create_app
from app.extensions import db as _db
from app.models.user import User, UserRole


@pytest.fixture(scope='function')
def app():
    app = create_app('testing')
    with app.app_context():
        _db.create_all()
        yield app
        _db.session.remove()
        _db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def authenticated_client(app, client):
    """Authenticated student client using Flask test session injection.

    Uses session_transaction() which works reliably with session_protection='basic'.
    The password_version is injected so user_loader accepts the session.
    """
    with app.app_context():
        user = User(
            email='student@test.com',
            display_name='Test Student',
            role=UserRole.STUDENT
        )
        user.set_password('Test@1234!')
        _db.session.add(user)
        _db.session.commit()
        user_id = user.id
        pv = user.password_version
    with client.session_transaction() as sess:
        sess['_user_id'] = str(user_id)
        sess['_fresh'] = True
        sess['password_version'] = pv
    return client


@pytest.fixture
def admin_client(app, client):
    """Authenticated admin client using Flask test session injection."""
    with app.app_context():
        admin = User(
            email='admin@test.com',
            display_name='Admin User',
            role=UserRole.ADMIN
        )
        admin.set_password('Admin@1234!')
        _db.session.add(admin)
        _db.session.commit()
        admin_id = admin.id
        pv = admin.password_version
    with client.session_transaction() as sess:
        sess['_user_id'] = str(admin_id)
        sess['_fresh'] = True
        sess['password_version'] = pv
    return client


@pytest.fixture
def security_app():
    """App with CSRF and rate-limiting enabled — used only by test_security.py."""
    app = create_app('testing')
    app.config['WTF_CSRF_ENABLED'] = True
    app.config['RATELIMIT_ENABLED'] = True
    with app.app_context():
        _db.create_all()
        yield app
        _db.session.remove()
        _db.drop_all()


@pytest.fixture
def security_client(security_app):
    return security_app.test_client()
