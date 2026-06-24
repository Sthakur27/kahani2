"""Auth: signed, expiring session tokens (HMAC via itsdangerous) plus the
FastAPI dependencies that resolve a Bearer token to a user. The server derives
the user from the verified token — clients can never assert an arbitrary
user_id. Set SECRET_KEY in the environment for production."""
import os

from fastapi import Depends, Header, HTTPException
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from sqlalchemy.orm import Session
from werkzeug.security import check_password_hash, generate_password_hash

from db import get_db
from models import User

SECRET_KEY = os.environ.get("SECRET_KEY", "dev-insecure-secret-change-me")
TOKEN_MAX_AGE = 7 * 24 * 3600  # 7 days
_signer = URLSafeTimedSerializer(SECRET_KEY, salt="storysim-auth")

# Re-exported so routers don't import werkzeug directly.
hash_password = generate_password_hash
verify_password = check_password_hash


def make_token(user_id: int) -> str:
    return _signer.dumps({"uid": user_id})


def read_token(token: str):
    try:
        data = _signer.loads(token, max_age=TOKEN_MAX_AGE)
        return data.get("uid")
    except (BadSignature, SignatureExpired):
        return None


def optional_user(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> User | None:
    """The user from a valid Bearer token, or None (anonymous)."""
    if not authorization or not authorization.startswith("Bearer "):
        return None
    uid = read_token(authorization[7:].strip())
    return db.get(User, uid) if uid is not None else None


def current_user(user: User | None = Depends(optional_user)) -> User:
    """Require authentication; 401 otherwise."""
    if user is None:
        raise HTTPException(status_code=401, detail="authentication required")
    return user


def admin_user(user: User = Depends(current_user)) -> User:
    """Require an admin user; 403 otherwise."""
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="admin only")
    return user
