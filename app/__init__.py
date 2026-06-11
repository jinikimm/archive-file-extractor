import os

import yaml
from flasgger import Swagger
from flask import Flask
from flask_migrate import Migrate
from sqlalchemy import text

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

    from .model import db

    db.init_app(app)
    Migrate(app, db)

    error_handlers(app)
    init_logger(app)

    with open("app/api/swagger.yaml") as f:
        template = yaml.safe_load(f)
    Swagger(app, template=template)

    from .api import analyze_api, extraction_api

    app.register_blueprint(extraction_api.bp)
    app.register_blueprint(analyze_api.bp)

    @app.get("/health")
    def health():
        try:
            db.session.execute(text("SELECT 1"))
            return {"status": "ok"}, 200
        except Exception:
            return {"status": "error"}, 500

    return app
