from flask import g, jsonify
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.exceptions import BadRequest


class Error(Exception):
    def __init__(self, status_code, code, message, details=None):
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details if details is not None else []


class ValidationError(Error):
    def __init__(self, details=None, message="Invalid snapshot payload"):
        super().__init__(400, "validation_error", message, details)


class NotFoundError(Error):
    def __init__(self, details=None, message="Resource not found"):
        super().__init__(404, "not_found", message, details)


class ConflictError(Error):
    def __init__(self, details=None, message="Conflict"):
        super().__init__(409, "conflict", message, details)


class ArchiveError(Error):
    def __init__(self, details=None, message="Archive processing failed"):
        super().__init__(500, "archive_error", message, details)


def error_handlers(app):
    def _request_id():
        return getattr(g, "request_id", None)

    @app.errorhandler(Error)
    def app_error(e):
        return (
            jsonify(
                {
                    "request_id": _request_id(),
                    "error": {
                        "code": e.code,
                        "message": e.message,
                        "details": e.details,
                    },
                }
            ),
            e.status_code,
        )

    @app.errorhandler(BadRequest)
    def bad_request(e):
        return (
            jsonify(
                {
                    "request_id": _request_id(),
                    "error": {
                        "code": "validation_error",
                        "message": "Invalid snapshot payload",
                        "details": [
                            {
                                "field": "body",
                                "message": "Malformed JSON",
                            }
                        ],
                    },
                }
            ),
            400,
        )

    @app.errorhandler(SQLAlchemyError)
    def database_error(e):
        return (
            jsonify(
                {
                    "request_id": _request_id(),
                    "error": {
                        "code": "database_error",
                        "message": "Database operation failed",
                        "details": [],
                    },
                }
            ),
            503,
        )

    @app.errorhandler(500)
    def internal_error(e):
        return (
            jsonify(
                {
                    "request_id": _request_id(),
                    "error": {
                        "code": "internal_error",
                        "message": "An unexpected error occurred.",
                        "details": [],
                    },
                }
            ),
            500,
        )
