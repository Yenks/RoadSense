"""
Flask dashboard app — Week 9.
"""

from flask import Flask
from flask_login import LoginManager

from app.config import SECRET_KEY
from app.database.db import get_session, init_db
from app.database.models import User


def create_app():
    app = Flask(
        __name__,
        template_folder="../dashboard/templates",
        static_folder="../dashboard/static",
    )
    app.config["SECRET_KEY"] = SECRET_KEY
    import os
    app.jinja_env.filters['basename'] = os.path.basename

    init_db()

    login_manager = LoginManager()
    login_manager.login_view = "login"
    login_manager.init_app(app)

    from app.auth import load_user_from_token

    @login_manager.user_loader
    def load_user(access_token):
        return load_user_from_token(access_token)

    from app.routes import register_routes
    register_routes(app)

    return app


if __name__ == "__main__":
    from app.config import FLASK_HOST, FLASK_PORT, DEBUG
    app = create_app()
    app.run(host=FLASK_HOST, port=FLASK_PORT, debug=DEBUG)