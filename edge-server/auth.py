from functools import wraps

from flask import jsonify, request
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer


class AuthManager:
    def __init__(self, db_module, secret_key: str, token_max_age: int, admin_token: str):
        self.db = db_module
        self.admin_token = admin_token
        self.serializer = URLSafeTimedSerializer(secret_key, salt="auth-token")
        self.token_max_age = token_max_age

    def issue_token(self, user_id: int) -> str:
        return self.serializer.dumps({"uid": int(user_id)})

    def verify_token(self, token: str):
        try:
            data = self.serializer.loads(token, max_age=self.token_max_age)
            return int(data.get("uid"))
        except (BadSignature, SignatureExpired, Exception):
            return None

    def get_bearer_token(self):
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            return auth[len("Bearer "):].strip()
        return None

    def get_current_user(self):
        token = self.get_bearer_token()
        if not token:
            return None
        uid = self.verify_token(token)
        if not uid:
            return None
        user = self.db.get_user_by_id(uid)
        if not user:
            return None
        user["roles"] = self.db.get_user_roles(uid)
        return user

    def is_admin_request(self, user=None, provided_token=None) -> bool:
        if provided_token == self.admin_token:
            return True
        if user is None:
            user = self.get_current_user()
        return bool(user and ("admin" in (user.get("roles") or [])))

    def auth_required(self, fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            user = self.get_current_user()
            if not user:
                return jsonify({"error": "unauthorized"}), 401
            request.current_user = user
            return fn(*args, **kwargs)

        return wrapper

    def admin_required(self, fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            provided = request.headers.get("X-Admin-Token")
            user = self.get_current_user()
            if not self.is_admin_request(user=user, provided_token=provided):
                return jsonify({"error": "admin required"}), 403
            if user:
                request.current_user = user
            return fn(*args, **kwargs)

        return wrapper
