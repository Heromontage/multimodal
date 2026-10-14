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

from .database import EmailVerification, LoginSession, User, get_db
from .mail import send_verification_email

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
    verification = db.get(EmailVerification, user.id)
    if verification is None or verification.verified_at is None:
        raise HTTPException(401, 'Verify your email address before signing in.')
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


class EmailAddress(BaseModel):
    model_config = ConfigDict(extra='forbid')
    email: EmailStr = Field(max_length=254)

    @field_validator('email', mode='before')
    @classmethod
    def normalize_email(cls, value):
        return value.strip().lower() if isinstance(value, str) else value


class VerifyEmail(BaseModel):
    model_config = ConfigDict(extra='forbid')
    token: str = Field(min_length=32, max_length=128)
    password: str = Field(min_length=8, max_length=128)


def issue_verification(user, db):
    record = db.get(EmailVerification, user.id)
    if record and record.verified_at:
        return
    now = datetime.utcnow()
    if record is None:
        record = EmailVerification(user_id=user.id, sent_count=0)
        db.add(record)
    if record.sent_at and now - record.sent_at < timedelta(minutes=1):
        return
    if not record.window_start or now - record.window_start >= timedelta(hours=1):
        record.window_start, record.sent_count = now, 0
    if record.sent_count >= 5:
        return
    token = secrets.token_urlsafe(32)
    record.token_hash = token_hash(token)
    record.expires_at = now + timedelta(minutes=30)
    record.sent_at = now
    record.sent_count += 1
    db.flush()
    try:
        send_verification_email(user.email, token)
    except Exception:
        db.rollback()
        # Never return SMTP credentials or a verification token to the browser/logs.
        raise HTTPException(503, 'Unable to send verification email. Please try again later or contact the app administrator.') from None
    db.commit()


@router.post('/signup', status_code=201)
def signup(credentials: Credentials, db: Session = Depends(get_db)):
    user = User(email=str(credentials.email), password_hash=password_hasher.hash(credentials.password))
    db.add(user)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, 'An account with this email already exists. Sign in or resend its verification email.')
    issue_verification(user, db)
    return {'verification_required': True, 'message': 'Check your inbox to verify your email before signing in.'}


@router.post('/resend-verification')
def resend_verification(address: EmailAddress, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == str(address.email)).with_for_update())
    if user:
        issue_verification(user, db)
    return {'message': 'If this address has an unverified account, a verification email has been sent. Allow one minute between requests; up to five emails per hour.'}


@router.post('/verify-email')
def verify_email(payload: VerifyEmail, db: Session = Depends(get_db)):
    # Lock user first, consistently with signin/resend, to serialize token consumption.
    user = db.scalar(select(User).join(EmailVerification, EmailVerification.user_id == User.id)
                     .where(EmailVerification.token_hash == token_hash(payload.token)).with_for_update())
    record = db.get(EmailVerification, user.id) if user else None
    now = datetime.utcnow()
    invalid = 'This link is invalid or expired, or the password is incorrect. Request a new email if needed.'
    if not record or record.verified_at or not record.expires_at or record.expires_at <= now:
        raise HTTPException(400, invalid)
    if user.locked_until and user.locked_until > now:
        raise HTTPException(429, 'Too many attempts. Please try again in 15 minutes.')
    if user.locked_until:
        user.failed_logins, user.locked_until = 0, None
    try:
        password_hasher.verify(user.password_hash, payload.password)
    except (VerificationError, InvalidHashError):
        user.failed_logins += 1
        if user.failed_logins >= 5:
            user.locked_until = now + timedelta(minutes=15)
        db.commit()
        raise HTTPException(400, invalid)
    record.verified_at = now
    record.token_hash = None
    record.expires_at = None
    user.failed_logins, user.locked_until = 0, None
    db.execute(delete(LoginSession).where(LoginSession.user_id == user.id))
    db.commit()
    return {'message': 'Email verified. You can now sign in.'}


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
    record = db.get(EmailVerification, user.id)
    if not record or not record.verified_at:
        db.commit()
        raise HTTPException(403, {'code': 'email_unverified', 'message': 'Verify your email address before signing in.'})
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
