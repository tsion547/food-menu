import datetime
from functools import wraps

import jwt
from flask import request, jsonify, current_app

JWT_ALGORITHM = 'HS256'


def generate_token(admin, expires_in_hours=2):
    """Create a signed JWT carrying the admin's id and role."""
    now = datetime.datetime.utcnow()
    payload = {
        "admin_id": admin.id,
        "username": admin.username,
        "role": admin.role,
        "iat": now,
        "exp": now + datetime.timedelta(hours=expires_in_hours),
    }
    token = jwt.encode(payload, current_app.config['SECRET_KEY'], algorithm=JWT_ALGORITHM)
    # PyJWT >= 2 returns a str already; older versions return bytes.
    if isinstance(token, bytes):
        token = token.decode('utf-8')
    return token


def decode_token(token):
    """Raises jwt.ExpiredSignatureError / jwt.InvalidTokenError on failure."""
    return jwt.decode(token, current_app.config['SECRET_KEY'], algorithms=[JWT_ALGORITHM])


def get_bearer_token():
    auth_header = request.headers.get('Authorization', '')
    if auth_header.startswith('Bearer '):
        return auth_header.split(' ', 1)[1].strip()
    return None


def admin_required(f):
    """Protects a route: 401 if the token is missing/invalid/expired,
    403 if the token is valid but doesn't carry the admin role."""
    @wraps(f)
    def wrapper(*args, **kwargs):
        token = get_bearer_token()

        if not token:
            return jsonify({"error": "Missing authentication token"}), 401

        try:
            payload = decode_token(token)
        except jwt.ExpiredSignatureError:
            return jsonify({"error": "Token has expired"}), 401
        except jwt.InvalidTokenError:
            return jsonify({"error": "Invalid token"}), 401

        if payload.get('role') != 'admin':
            return jsonify({"error": "Admin privileges required"}), 403

        request.admin_id = payload.get('admin_id')
        request.admin_username = payload.get('username')
        request.admin_role = payload.get('role')

        return f(*args, **kwargs)

    return wrapper
