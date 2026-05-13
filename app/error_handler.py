from flask import jsonify

def error_handlers(app):
    @app.errorhandler(400)
    def bad_request(e):
        return jsonify(error="bad_request", message=str(e)), 400

    @app.errorhandler(404)
    def not_found(e):
        return jsonify(error="not_found", message=str(e)), 404

    @app.errorhandler(500)
    def internal_error(e):
        return (
            jsonify(error="internal_error", message="An unexpected error occurred."),
            500,
        )