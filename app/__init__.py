import os
from queue import Queue

from flask import Flask
from flask_migrate import Migrate

from .error_handler import error_handlers

queue = Queue()

def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)

    if test_config is None:
        app.config.from_object("app.config.Config")
    else:
        app.config.update(test_config)

    os.makedirs(app.instance_path, exist_ok=True)

    @app.get("/healthz")
    def healthz():
        return {"status": "ok"}, 200

    from .model import db
    
    db.init_app(app)
    Migrate(app, db)

    from . import extraction_api
    app.register_blueprint(extraction_api.bp)

    error_handlers(app)
    from .worker import set_worker
    set_worker(app, app.config.get("CONCURRENCY", 4))

    return app