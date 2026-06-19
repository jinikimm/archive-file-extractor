import multiprocessing
import os
import signal
import sys
import threading

import yaml
from flasgger import Swagger
from flask import Flask
from flask_migrate import Migrate
from sqlalchemy import text

thread_shutdown_event = threading.Event()
process_shutdown_event = multiprocessing.Event()


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)

    if test_config is None:
        app.config.from_object("app.config.Config")
    else:
        app.config.update(test_config)

    os.makedirs(app.instance_path, exist_ok=True)

    from .db.model import db
    db.init_app(app)
    Migrate(app, db)

    from .logger import init_logger
    init_logger(app)

    from .error_handler import error_handlers
    error_handlers(app)

    from .api import register_apis
    register_apis(app)

    with open("docs/api/swagger.yaml") as f:
        template = yaml.safe_load(f)
    Swagger(app, template=template)

    @app.get("/health")
    def health():
        try:
            db.session.execute(text("SELECT 1"))
            return {"status": "ok"}, 200
        except Exception:
            return {"status": "error"}, 500

    def handle_shutdown(signum, frame):
        global thread_shutdown_event, process_shutdown_event
        thread_shutdown_event.set()
        process_shutdown_event.set()

        app.logger.info("Received shutdown signal.")

        for thread in threading.enumerate():
            if not thread.daemon and thread != threading.current_thread():
                thread.join(timeout=5)
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)

    return app
