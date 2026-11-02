import os
from pathlib import Path

from flask import Flask, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
from werkzeug.exceptions import HTTPException

from .models import db


def create_app(test_config=None):
    load_dotenv(Path(__file__).resolve().parents[2] / ".env")
    app = Flask(__name__, instance_relative_config=True)
    Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    database_url = os.environ.get(
        "DATABASE_URL",
        "postgresql+psycopg://glamride:glamride@localhost:5432/glamride",
    )
    if database_url.startswith("postgres://"):
        database_url = database_url.replace(
            "postgres://", "postgresql+psycopg://", 1
        )
    elif database_url.startswith("postgresql://"):
        database_url = database_url.replace(
            "postgresql://", "postgresql+psycopg://", 1
        )
    app.config.from_mapping(
        SECRET_KEY=os.environ.get("SECRET_KEY", "local-development-key-change-before-deploy"),
        SQLALCHEMY_DATABASE_URI=database_url,
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        TOKEN_TTL_SECONDS=60 * 60 * 24,
        OTP_TTL_SECONDS=5 * 60,
        OTP_MAX_ATTEMPTS=5,
        DEMO_OTP_ENABLED=os.environ.get("APP_ENV", "development") != "production",
        DEMO_SEED=os.environ.get("APP_ENV", "development") != "production",
        MAX_CONTENT_LENGTH=8 * 1024 * 1024,
        UPLOAD_FOLDER=str(Path(app.instance_path, "private_uploads")),
        CORS_ORIGIN=os.environ.get("FRONTEND_ORIGIN", "http://localhost:5173"),
    )
    if test_config:
        app.config.update(test_config)
    if os.environ.get("APP_ENV") == "production" and app.config["SECRET_KEY"] == "local-development-key-change-before-deploy":
        raise RuntimeError("Set a unique SECRET_KEY before running in production.")

    db.init_app(app)
    CORS(app, resources={r"/api/*": {"origins": app.config["CORS_ORIGIN"]}})

    from .routes import api

    app.register_blueprint(api, url_prefix="/api")

    @app.errorhandler(HTTPException)
    def handle_http_error(error):
        return jsonify(error=error.description), error.code

    @app.errorhandler(Exception)
    def handle_unexpected_error(error):
        app.logger.exception("Unhandled request error")
        return jsonify(error="An unexpected server error occurred."), 500

    with app.app_context():
        db.create_all()

    return app
