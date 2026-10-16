from flask import render_template, jsonify, request


def register_error_handlers(app):
    @app.errorhandler(400)
    def bad_request(e):
        if _wants_json():
            return jsonify({'error': str(e.description)}), 400
        return render_template('errors/400.html', error=e), 400

    @app.errorhandler(403)
    def forbidden(e):
        if _wants_json():
            return jsonify({'error': 'Forbidden'}), 403
        return render_template('errors/403.html', error=e), 403

    @app.errorhandler(404)
    def not_found(e):
        if _wants_json():
            return jsonify({'error': 'Not found'}), 404
        return render_template('errors/404.html', error=e), 404

    @app.errorhandler(413)
    def request_entity_too_large(e):
        if _wants_json():
            return jsonify({'error': 'File too large'}), 413
        return render_template('errors/413.html', error=e), 413

    @app.errorhandler(429)
    def too_many_requests(e):
        if _wants_json():
            return jsonify({'error': 'Too many requests. Please slow down.'}), 429
        return render_template('errors/404.html', error=e), 429

    @app.errorhandler(500)
    def internal_error(e):
        if _wants_json():
            return jsonify({'error': 'An internal error occurred.'}), 500
        return render_template('errors/500.html', error=e), 500


def _wants_json():
    """Returns True if the client prefers JSON."""
    return (
        request.is_json
        or request.accept_mimetypes.best == 'application/json'
        or request.path.startswith('/api/')
        or request.path.startswith('/auth/')
        or request.path.startswith('/admin/documents')
    )
