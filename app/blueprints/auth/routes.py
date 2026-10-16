import re
import hmac
from flask import request, jsonify, session as flask_session
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash
from app.blueprints.auth import auth_bp
from app.extensions import db, limiter
from app.models.user import User, UserRole
from app.utils.audit import log_audit_event
from app.utils.security import strip_html

_DUMMY_HASH = generate_password_hash('__dummy__', method='pbkdf2:sha256:600000')

EMAIL_RE = re.compile(r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$')
PASSWORD_RE = re.compile(r'^(?=.*[A-Z])(?=.*\d)(?=.*[^A-Za-z0-9]).{8,128}$')


@auth_bp.route('/register', methods=['POST'])
@limiter.limit('10 per minute')
def register():
    data = request.get_json(silent=True) or {}
    email = data.get('email', '').strip().lower()
    password = data.get('password', '')
    confirm_password = data.get('confirm_password', '')
    display_name = strip_html(data.get('display_name', '') or '')[:100]

    if not email or len(email) > 255 or not EMAIL_RE.match(email):
        return jsonify({'error': 'Please enter a valid email address.'}), 400
    if not password or not PASSWORD_RE.match(password):
        return jsonify({'error': 'Password must be 8+ characters with uppercase, digit, and special character.'}), 400
    if password != confirm_password:
        return jsonify({'error': 'Passwords do not match.'}), 400

    existing = db.session.execute(db.select(User).filter_by(email=email)).scalar_one_or_none()
    if existing:
        return jsonify({'error': 'Registration failed. Please check your input.'}), 400

    try:
        user = User(
            email=email,
            display_name=display_name or email.split('@')[0],
            role=UserRole.STUDENT
        )
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Registration failed. Please try again.'}), 400

    login_user(user)
    flask_session['password_version'] = user.password_version

    return jsonify({
        'message': 'Account created.',
        'user': {'id': user.id, 'email': user.email, 'display_name': user.display_name, 'role': user.role.value}
    }), 201


@auth_bp.route('/login', methods=['POST'])
@limiter.limit('20 per minute')
def login():
    data = request.get_json(silent=True) or {}
    email = data.get('email', '').strip().lower()
    password = data.get('password', '')
    remember_me = bool(data.get('remember_me', False))

    user = db.session.execute(db.select(User).filter_by(email=email)).scalar_one_or_none()

    if user is None:
        hmac.compare_digest(_DUMMY_HASH, _DUMMY_HASH)
        return jsonify({'error': 'Invalid email or password.'}), 401
    if not user.check_password(password):
        return jsonify({'error': 'Invalid email or password.'}), 401
    if not user.is_active:
        return jsonify({'error': 'Invalid email or password.'}), 401

    flask_session['password_version'] = user.password_version
    login_user(user, remember=remember_me)

    return jsonify({
        'message': 'Logged in.',
        'user': {'id': user.id, 'email': user.email, 'display_name': user.display_name, 'role': user.role.value}
    }), 200


@auth_bp.route('/logout', methods=['POST'])
@login_required
def logout():
    logout_user()
    flask_session.clear()
    return jsonify({'message': 'Logged out.'}), 200


@auth_bp.route('/me', methods=['GET'])
@login_required
def me():
    return jsonify({
        'user': {'id': current_user.id, 'email': current_user.email,
                 'display_name': current_user.display_name, 'role': current_user.role.value}
    }), 200


@auth_bp.route('/profile', methods=['PUT'])
@login_required
def update_profile():
    data = request.get_json(silent=True) or {}
    display_name = strip_html(str(data.get('display_name', '') or '').strip())[:100]
    if not display_name:
        return jsonify({'error': 'Display name is required.'}), 400
    try:
        current_user.display_name = display_name
        db.session.commit()
    except Exception:
        db.session.rollback()
        return jsonify({'error': 'An error occurred.'}), 500
    return jsonify({'user': {'id': current_user.id, 'display_name': current_user.display_name}}), 200


@auth_bp.route('/password', methods=['PUT'])
@login_required
def change_password():
    data = request.get_json(silent=True) or {}
    current_password = data.get('current_password', '')
    new_password = data.get('new_password', '')
    confirm_new = data.get('confirm_new_password', '')

    if not current_user.check_password(current_password):
        return jsonify({'error': 'Current password is incorrect.'}), 400
    if not new_password or not PASSWORD_RE.match(new_password):
        return jsonify({'error': 'Password must be 8+ characters with uppercase, digit, and special character.'}), 400
    if new_password != confirm_new:
        return jsonify({'error': 'New passwords do not match.'}), 400

    try:
        current_user.set_password(new_password)
        flask_session['password_version'] = current_user.password_version
        db.session.commit()
    except Exception:
        db.session.rollback()
        return jsonify({'error': 'An error occurred.'}), 500
    return jsonify({'message': 'Password updated.'}), 200


@auth_bp.route('/account', methods=['DELETE'])
@login_required
def delete_account():
    data = request.get_json(silent=True) or {}
    if not current_user.check_password(data.get('password', '')):
        return jsonify({'error': 'Incorrect password.'}), 400
    try:
        current_user.is_active = False
        db.session.commit()
    except Exception:
        db.session.rollback()
        return jsonify({'error': 'An error occurred.'}), 500
    logout_user()
    flask_session.clear()
    return '', 204
