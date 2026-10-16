from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_wtf.csrf import CSRFProtect

db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
login_manager.login_view = 'pages.login'
login_manager.login_message = 'Please log in to access this page.'
# NOTE: "strong" protection clears the entire session (not just marks it non-fresh)
# when Flask-Login detects a change in the client's IP+User-Agent fingerprint.
# On mobile networks with dynamic IP addresses this can silently log students out
# mid-session. The password_version check in user_loader already provides strong
# security against session theft after a password change. If silent mobile logouts
# become a reported issue, downgrade to session_protection = "basic" — the
# password_version mechanism compensates for the reduced protection.
login_manager.session_protection = 'basic'
# NOTE: Downgraded from 'strong' to 'basic' because 'strong' clears the entire
# session when the client IP or User-Agent changes (common on mobile networks).
# Security is maintained by the password_version check in user_loader: every
# password change increments password_version and any existing session/cookie
# with a stale version is rejected on the next request. This is a stronger and
# more explicit guarantee than the IP+UA fingerprint 'strong' mode provides.
limiter = Limiter(
    key_func=get_remote_address,
    storage_uri='memory://',       # explicit in-memory — no external Redis needed
    default_limits=['200 per day', '50 per hour'],
)
csrf = CSRFProtect()
