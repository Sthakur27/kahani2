"""Auth routes: signup/login issue a signed session token the client sends as
`Authorization: Bearer <token>`. The server trusts the token, not a user_id."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from auth import current_user, hash_password, make_token, verify_password
from db import get_db
from models import User
from schemas import Credentials
from serializers import user_to_dict

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _auth_payload(user: User) -> dict:
    return {"user": user_to_dict(user), "token": make_token(user.id)}


@router.post("/signup", status_code=201)
def signup(body: Credentials, db: Session = Depends(get_db)):
    username = (body.username or "").strip()
    password = body.password or ""
    if len(username) < 2 or len(password) < 4:
        raise HTTPException(400, "username (2+) and password (4+) required")
    if db.scalar(select(User).where(User.username == username)):
        raise HTTPException(409, "username taken")
    user = User(username=username, password_hash=hash_password(password))
    db.add(user)
    db.commit()
    db.refresh(user)
    return _auth_payload(user)


@router.post("/login")
def login(body: Credentials, db: Session = Depends(get_db)):
    username = (body.username or "").strip()
    password = body.password or ""
    user = db.scalar(select(User).where(User.username == username))
    if (
        user is None
        or not user.password_hash
        or not verify_password(user.password_hash, password)
    ):
        raise HTTPException(401, "invalid username or password")
    return _auth_payload(user)


@router.get("/me")
def auth_me(user: User = Depends(current_user)):
    """Resolve the current token to a user (lets the client validate a stored token)."""
    return user_to_dict(user)
