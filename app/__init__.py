import importlib
import click
from flask import Flask
from config import config


def create_app(config_name: str = 'development') -> Flask:
    app = Flask(
        __name__,
        static_folder='../static',
        template_folder='../templates'
    )
    app.config.from_object(config[config_name])

    # Validate required secrets at startup (after subclass values are in effect)
    if not app.config.get('SECRET_KEY'):
        raise RuntimeError('SECRET_KEY environment variable is not set.')
    # Skip GROQ_API_KEY check for testing config (it's set to 'test-api-key')
    if config_name != 'testing' and not app.config.get('GROQ_API_KEY'):
        raise RuntimeError('GROQ_API_KEY environment variable is not set.')

    # Initialize extensions
    from app.extensions import db, migrate, login_manager, limiter, csrf
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    limiter.init_app(app)
    csrf.init_app(app)

    # Configure user_loader with remember-me bypass for password_version check
    @login_manager.user_loader
    def load_user(user_id):
        from flask import session as flask_session
        from app.models.user import User
        user = db.session.get(User, int(user_id))
        if user is None or not user.is_active:
            return None
        stored_version = flask_session.get('password_version')
        if stored_version is None:
            # Remember-me cookie load: session is empty (Flask-Login creates a fresh
            # session for cookie-based logins, so flask_session has no password_version).
            # Populate the session so all subsequent requests have a version to compare.
            # This means the remember-me cookie is accepted once per browser session;
            # any future password change will be detected on the next request.
            flask_session['password_version'] = user.password_version
        elif stored_version != user.password_version:
            # Password was changed on another device — invalidate this session.
            return None
        return user

    # Register blueprints
    from app.blueprints.auth import auth_bp
    from app.blueprints.chat import chat_bp
    from app.blueprints.documents import documents_bp
    from app.blueprints.admin import admin_bp
    from app.blueprints.pages import pages_bp

    app.register_blueprint(pages_bp)
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(chat_bp, url_prefix='/api')
    app.register_blueprint(documents_bp, url_prefix='/api')
    app.register_blueprint(admin_bp, url_prefix='/admin')

    # Exempt JSON API blueprints from CSRF — they are protected by
    # Flask-Login session cookies (login_required). CSRF only matters
    # for cross-origin state-changing form submissions; all our API
    # calls are same-origin fetch() with credentials:'same-origin'.
    csrf.exempt(auth_bp)
    csrf.exempt(chat_bp)
    csrf.exempt(documents_bp)
    csrf.exempt(admin_bp)

    # Register error handlers
    from app.errors.handlers import register_error_handlers
    register_error_handlers(app)

    # Initialize embedder and vector store
    from app.rag.embedder import SentenceTransformerEmbedder
    from app.rag.vector_store import FAISSVectorStore
    from pathlib import Path

    embedder = SentenceTransformerEmbedder(app.config.get('EMBEDDING_MODEL'))
    vector_store = FAISSVectorStore(Path(app.config['VECTOR_STORE_PATH']))
    app.extensions['embedder'] = embedder
    app.extensions['vector_store'] = vector_store

    # Initialize AI provider via config-driven importlib (AI_PROVIDER_CLASS)
    provider_class_path = app.config.get('AI_PROVIDER_CLASS', 'app.ai.groq_provider.GroqProvider')
    module_path, class_name = provider_class_path.rsplit('.', 1)
    provider_module = importlib.import_module(module_path)
    ProviderClass = getattr(provider_module, class_name)

    provider = ProviderClass(
        api_key=app.config.get('GROQ_API_KEY', ''),
        model_id=app.config.get('GROQ_MODEL_ID', 'llama-3.3-70b-versatile'),
    )

    # Validate model at startup — non-fatal if the API is unreachable
    # Skip validation for testing config to avoid network calls with test key
    if config_name != 'testing':
        with app.app_context():
            if not provider.validate_model(app.config.get('GROQ_MODEL_ID', '')):
                app.logger.warning(
                    "Could not verify GROQ_MODEL_ID '%s' at startup. "
                    "The model ID may still be valid; proceeding.",
                    app.config.get('GROQ_MODEL_ID')
                )
    app.extensions['ai_provider'] = provider

    # Initialize job runner (must be last — it needs the app object)
    from app.ingestion.job_runner import get_job_runner
    get_job_runner().init_app(app)

    # Automatically ensure tables exist on startup (SQLite, PostgreSQL/Supabase, Railway)
    with app.app_context():
        try:
            from app.models.user import User
            from app.models.chat import ChatSession, ChatMessage, SavedPrompt
            from app.models.document import Document, DocumentChunk, DocumentProcessingJob
            from app.models.feedback import Feedback
            from app.models.audit import AuditEvent
            db.create_all()
        except Exception as e:
            app.logger.warning('db.create_all() exception on startup: %s', e)

    # Register CLI commands
    _register_cli(app)

    return app


def _register_cli(app):
    @app.cli.command('create-admin')
    @click.argument('email')
    def create_admin(email):
        """Promote an existing user to admin, or create one if not found."""
        import getpass
        from app.extensions import db
        from app.models.user import User, UserRole

        password = getpass.getpass('Password: ')
        confirm = getpass.getpass('Confirm:  ')
        if password != confirm:
            click.echo('Passwords do not match.')
            return

        with app.app_context():
            user = db.session.execute(
                db.select(User).filter_by(email=email.strip().lower())
            ).scalar_one_or_none()

            if user is None:
                user = User(
                    email=email.strip().lower(),
                    display_name=email.split('@')[0],
                    role=UserRole.ADMIN
                )
                user.set_password(password)
                db.session.add(user)
                click.echo(f'Created admin user: {email}')
            else:
                user.role = UserRole.ADMIN
                user.set_password(password)
                click.echo(f'Promoted existing user to admin: {email}')

            db.session.commit()
