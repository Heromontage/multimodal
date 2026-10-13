"""Email/password authentication with revocable, opaque cookie sessions."""
from datetime import datetime, timedelta
import hashlib
import os
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .database import LoginSession, User, get_db

router = APIRouter()
COOKIE = 'coronary_session'
SESSION_SECONDS = 7 * 24 * 60 * 60
password_hasher = PasswordHasher()
dummy_hash = password_hasher.hash(secrets.token_urlsafe(32))


class Credentials(BaseModel):
    model_config = ConfigDict(extra='forbid')
    email: EmailStr = Field(max_length=254)
    password: str = Field(min_length=8, max_length=128)

    @field_validator('email', mode='before')
    @classmethod
    def normalize_email(cls, value):
        return value.strip().lower() if isinstance(value, str) else value


def token_hash(token):
    return hashlib.sha256(token.encode()).hexdigest()


def secure_cookie():
    return os.environ.get('COOKIE_SECURE', 'false').lower() == 'true'


def current_user(request: Request, db: Session = Depends(get_db)):
    token = request.cookies.get(COOKIE)
    if not token or len(token) > 128:
        raise HTTPException(401, 'Please sign in to continue.')
    session = db.get(LoginSession, token_hash(token))
    if session is None or session.expires_at <= datetime.utcnow():
        raise HTTPException(401, 'Your session has expired. Please sign in again.')
    user = db.get(User, session.user_id)
    if user is None:
        raise HTTPException(401, 'Please sign in to continue.')
    return user


def account_data(user):
    return {'user': {'email': user.email}, 'inputs': user.saved_inputs}


def create_session(user, request, response, db):
    old_token = request.cookies.get(COOKIE)
    if old_token:
        db.execute(delete(LoginSession).where(LoginSession.token_hash == token_hash(old_token)))
    db.execute(delete(LoginSession).where(
        LoginSession.user_id == user.id, LoginSession.expires_at <= datetime.utcnow()))
    token = secrets.token_urlsafe(32)
    db.add(LoginSession(token_hash=token_hash(token), user_id=user.id,
                        expires_at=datetime.utcnow() + timedelta(seconds=SESSION_SECONDS)))
    db.commit()
    response.set_cookie(COOKIE, token, max_age=SESSION_SECONDS, httponly=True,
                        secure=secure_cookie(), samesite='strict', path='/')


@router.post('/signup', status_code=201)
def signup(credentials: Credentials, request: Request, response: Response,
           db: Session = Depends(get_db)):
    user = User(email=str(credentials.email), password_hash=password_hasher.hash(credentials.password))
    db.add(user)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, 'An account with this email already exists. Please sign in.')
    create_session(user, request, response, db)
    return account_data(user)


@router.post('/signin')
def signin(credentials: Credentials, request: Request, response: Response,
           db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == str(credentials.email)).with_for_update())
    now = datetime.utcnow()
    if user and user.locked_until and user.locked_until > now:
        raise HTTPException(429, 'Too many sign-in attempts. Please try again in 15 minutes.')
    if user and user.locked_until:
        user.failed_logins = 0
        user.locked_until = None
    try:
        password_hasher.verify(user.password_hash if user else dummy_hash, credentials.password)
        verified = user is not None
    except (VerificationError, InvalidHashError):
        verified = False
    if not verified:
        if user:
            user.failed_logins += 1
            if user.failed_logins >= 5:
                user.locked_until = now + timedelta(minutes=15)
            db.commit()
        raise HTTPException(401, 'Email or password is incorrect.')
    user.failed_logins = 0
    user.locked_until = None
    if password_hasher.check_needs_rehash(user.password_hash):
        user.password_hash = password_hasher.hash(credentials.password)
    create_session(user, request, response, db)
    return account_data(user)


@router.get('/session')
def session(user: User = Depends(current_user)):
    return account_data(user)


@router.post('/signout')
def signout(request: Request, response: Response, db: Session = Depends(get_db)):
    token = request.cookies.get(COOKIE)
    if token:
        db.execute(delete(LoginSession).where(LoginSession.token_hash == token_hash(token)))
        db.commit()
    response.delete_cookie(COOKIE, path='/', httponly=True, secure=secure_cookie(), samesite='strict')
    return {'ok': True}
