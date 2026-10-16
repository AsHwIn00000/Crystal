from flask import Blueprint

documents_bp = Blueprint('documents', __name__)

from app.blueprints.documents import routes  # noqa: F401, E402
