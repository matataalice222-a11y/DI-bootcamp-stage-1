from functools import wraps

from flask import current_app, g, jsonify, request
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from .models import User, db


def issue_token(user):
    serializer = URLSafeTimedSerializer(current_app.config["SECRET_KEY"], salt="glamride-auth")
    return serializer.dumps({"user_id": user.id})


def authenticate(roles=None):
    def decorator(handler):
        @wraps(handler)
        def wrapped(*args, **kwargs):
            authorization = request.headers.get("Authorization", "")
            scheme, _, token = authorization.partition(" ")
            if scheme.lower() != "bearer" or not token:
                return jsonify(error="Please sign in to continue."), 401

            serializer = URLSafeTimedSerializer(
                current_app.config["SECRET_KEY"], salt="glamride-auth"
            )
            try:
                payload = serializer.loads(
                    token, max_age=current_app.config["TOKEN_TTL_SECONDS"]
                )
            except SignatureExpired:
                return jsonify(error="Your session expired. Please sign in again."), 401
            except BadSignature:
                return jsonify(error="Your session is invalid. Please sign in again."), 401

            user = db.session.get(User, payload.get("user_id"))
            if user is None:
                return jsonify(error="This account is no longer available."), 401
            if roles and user.role not in roles:
                return jsonify(error="You do not have permission to do that."), 403
            g.current_user = user
            return handler(*args, **kwargs)

        return wrapped

    return decorator
