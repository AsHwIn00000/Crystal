import os
from datetime import timedelta
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


class Config:
    # Use os.getenv() (returns None if absent) so the class body does not raise
    # KeyError at import time. Required values are validated in create_app() after
    # the subclass's overrides are already in effect.
    SECRET_KEY = os.getenv('SECRET_KEY', 'change-me-in-production')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    @staticmethod
    def _database_uri():
        url = os.getenv('DATABASE_URL', f'sqlite:///{BASE_DIR / "crystal.db"}')
        if url.startswith('postgres://'):
            url = url.replace('postgres://', 'postgresql://', 1)
        return url

    SQLALCHEMY_DATABASE_URI = _database_uri.__func__()

    @staticmethod
    def _engine_options():
        db_url = os.getenv('DATABASE_URL', '')
        if db_url.startswith('postgresql') or db_url.startswith('postgres'):
            return {
                'pool_pre_ping': True,
                'pool_recycle': 280,
                'pool_timeout': 10,
                'connect_args': {
                    'connect_timeout': 8,
                    'options': '-c statement_timeout=15000'
                }
            }
        return {}  # SQLite needs no pool config

    SQLALCHEMY_ENGINE_OPTIONS = _engine_options.__func__()
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    SESSION_COOKIE_SECURE = True
    REMEMBER_COOKIE_HTTPONLY = True
    PERMANENT_SESSION_LIFETIME = timedelta(hours=8)
    WTF_CSRF_ENABLED = True
    # Tell Flask-WTF to accept CSRF token from the X-CSRFToken request header.
    # This is required for JSON API calls made via fetch() from the frontend.
    WTF_CSRF_HEADERS = ['X-CSRFToken']
    # Don't require HTTPS for CSRF cookie in development
    WTF_CSRF_SSL_STRICT = False
    # Exempt JSON-only API endpoints from origin check
    WTF_CSRF_TIME_LIMIT = None  # tokens don't expire (avoids form timeout issues)
    RATELIMIT_STORAGE_URL = os.getenv('RATELIMIT_STORAGE_URL', 'memory://')
    RATELIMIT_DEFAULT = '200 per day;50 per hour'
    RATELIMIT_ENABLED = True
    # AI
    GROQ_API_KEY = os.getenv('GROQ_API_KEY')  # None default — validated in create_app
    GROQ_MODEL_ID = os.getenv('GROQ_MODEL_ID', 'llama-3.3-70b-versatile')
    AI_PROVIDER_CLASS = os.getenv('AI_PROVIDER_CLASS', 'app.ai.groq_provider.GroqProvider')
    # RAG
    EMBEDDING_MODEL = os.getenv('EMBEDDING_MODEL', 'all-MiniLM-L6-v2')
    VECTOR_STORE_PATH = str(BASE_DIR / 'vector_store')
    TOP_K_RETRIEVAL = int(os.getenv('RAG_TOP_K', '5'))
    RELEVANCE_THRESHOLD = float(os.getenv('RAG_RELEVANCE_THRESHOLD', '0.3'))
    # Upload
    UPLOAD_FOLDER = str(BASE_DIR / 'uploads')
    MAX_CONTENT_LENGTH = int(os.getenv('MAX_FILE_SIZE_MB', '50')) * 1024 * 1024
    CHUNK_SIZE = int(os.getenv('CHUNK_SIZE', '500'))
    CHUNK_OVERLAP = int(os.getenv('CHUNK_OVERLAP', '50'))


class DevelopmentConfig(Config):
    DEBUG = True
    SESSION_COOKIE_SECURE = False
    WTF_CSRF_ENABLED = False   # disabled in dev — API uses session auth, no CSRF needed
    SQLALCHEMY_DATABASE_URI = os.getenv(
        'DATABASE_URL', f'sqlite:///{BASE_DIR / "crystalai_dev.db"}'
    )


class TestingConfig(Config):
    TESTING = True
    DEBUG = True
    WTF_CSRF_ENABLED = False
    RATELIMIT_ENABLED = False
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    SECRET_KEY = 'test-secret-key-crystal'
    GROQ_API_KEY = 'test-api-key'
    SESSION_COOKIE_SECURE = False
    VECTOR_STORE_PATH = '/tmp/crystal_test_vectors'
    UPLOAD_FOLDER = '/tmp/crystal_test_uploads'


class ProductionConfig(Config):
    SESSION_COOKIE_SECURE = True
    DEBUG = False


config = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig,
}
