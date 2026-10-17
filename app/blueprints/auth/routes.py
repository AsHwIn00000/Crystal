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
        return jsonify({'error': 'An account with this email already exists. Please Sign In instead.'}), 400

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
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Registration failed: {str(e)}'}), 400

    try:
        login_user(user)
        flask_session['password_version'] = user.password_version
    except Exception as e:
        import traceback
        traceback.print_exc()

    return jsonify({
        'message': 'Account created.',
        'user': {'id': user.id, 'email': user.email, 'display_name': user.display_name, 'role': getattr(user.role, 'value', str(user.role))}
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


@auth_bp.route('/forgot-password', methods=['POST'])
@limiter.limit('5 per minute')
def forgot_password():
    data = request.get_json(silent=True) or {}
    email = data.get('email', '').strip().lower()

    if not email:
        return jsonify({'error': 'Email is required.'}), 400

    user = db.session.execute(db.select(User).filter_by(email=email)).scalar_one_or_none()
    if not user or not user.is_active:
        # Prevent user enumeration: always return friendly success response
        return jsonify({
            'message': 'If an account exists with this email, a reset code has been processed.'
        }), 200

    # Generate a secure timed reset token
    import secrets
    from itsdangerous import URLSafeTimedSerializer
    from flask import current_app

    serializer = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
    token = serializer.dumps(user.email, salt='password-reset-salt')

    current_app.logger.info("Password reset requested for %s. Reset Token: %s", user.email, token)

    return jsonify({
        'message': 'Password reset verified. You may now choose your new password.',
        'reset_token': token
    }), 200


@auth_bp.route('/reset-password', methods=['POST'])
@limiter.limit('5 per minute')
def reset_password():
    data = request.get_json(silent=True) or {}
    token = data.get('token', '')
    new_password = data.get('new_password', '')
    confirm_new = data.get('confirm_new_password', '')

    if not token:
        return jsonify({'error': 'Reset token is missing or expired.'}), 400

    if not new_password or not PASSWORD_RE.match(new_password):
        return jsonify({'error': 'Password must be 8+ characters with uppercase, digit, and special character.'}), 400
    if new_password != confirm_new:
        return jsonify({'error': 'Passwords do not match.'}), 400

    from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature
    from flask import current_app

    serializer = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
    try:
        email = serializer.loads(token, salt='password-reset-salt', max_age=1800)  # 30 min expiration
    except (SignatureExpired, BadSignature):
        return jsonify({'error': 'Reset link or token has expired or is invalid. Please request a new one.'}), 400

    user = db.session.execute(db.select(User).filter_by(email=email)).scalar_one_or_none()
    if not user or not user.is_active:
        return jsonify({'error': 'User not found.'}), 404

    try:
        user.set_password(new_password)
        db.session.commit()
    except Exception:
        db.session.rollback()
        return jsonify({'error': 'Could not update password. Please try again.'}), 500

    return jsonify({'message': 'Password has been successfully reset! You can now sign in.'}), 200


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
