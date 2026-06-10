import os
from queue import Queue

from flask import Flask
from flask_migrate import Migrate

from .error_handler import error_handlers
from .logger import init_logger

executor = None

def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)

    if test_config is None:
        app.config.from_object("app.config.Config")
    else:
        app.config.update(test_config)

    os.makedirs(app.instance_path, exist_ok=True)

    @app.get("/health")
    def health():
        return {"status": "ok"}, 200

    from .model import db
    
    db.init_app(app)
    Migrate(app, db)

    error_handlers(app)
    init_logger(app)

    from .api import extraction_api
    app.register_blueprint(extraction_api.bp)
    from .api import analyze_api
    app.register_blueprint(analyze_api.bp)

    return app