"""Flask application factory pro pubkvíz."""
import os
from datetime import timedelta

from flask import Flask, abort, send_from_directory

from .config import Config
from . import db as db_module


def create_app():
    app = Flask(
        __name__,
        template_folder="../templates",
        static_folder="../static",
    )
    app.config.from_object(Config)
    app.permanent_session_lifetime = timedelta(hours=12)

    os.makedirs(app.config["MEDIA_DIR"], exist_ok=True)
    db_module.init_db(app)
    app.teardown_appcontext(db_module.close_db)

    from . import views_player, views_projector, views_admin
    app.register_blueprint(views_player.bp)
    app.register_blueprint(views_projector.bp)
    app.register_blueprint(views_admin.bp)

    @app.route("/media/<path:filename>")
    def media(filename):
        """Obrázky otázek. Na PythonAnywhere je lepší namapovat /media/
        jako statickou složku (viz DEPLOY.md) — tahle route je fallback."""
        path = os.path.join(app.config["MEDIA_DIR"], filename)
        if not os.path.isfile(path):
            abort(404)
        return send_from_directory(app.config["MEDIA_DIR"], filename)

    return app
