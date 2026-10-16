import re
from functools import wraps
from flask import abort
from flask_login import current_user


def admin_required(f):
    """Decorator that requires the current user to have admin role."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role.value != 'admin':
            abort(403)
        return f(*args, **kwargs)
    return decorated


def sanitize_filename(filename: str) -> str:
    """Remove dangerous characters from a filename."""
    # Keep only alphanumerics, spaces, dots, hyphens, underscores
    name = re.sub(r'[^\w\s.\-]', '', filename)
    name = name.strip()
    return name or 'unnamed'


def strip_html(text: str) -> str:
    """Remove all HTML tags from text."""
    return re.sub(r'<[^>]+>', '', text or '').strip()
