"""Account storage and database sessions."""
from datetime import datetime
from functools import lru_cache
import os

from fastapi import HTTPException
from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, URL, create_engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = 'users'
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(254), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    saved_inputs: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    saved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    failed_logins: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class LoginSession(Base):
    __tablename__ = 'login_sessions'
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime, index=True)


@lru_cache
def get_engine():
    url = os.environ.get('DATABASE_URL')
    if not url:
        if not os.environ.get('DB_HOST'):
            raise RuntimeError('Configure DATABASE_URL or DB_HOST before starting the API.')
        url = URL.create('mysql+pymysql',
            username=os.environ['DB_USER'], password=os.environ['DB_PASSWORD'],
            host=os.environ['DB_HOST'], port=int(os.environ.get('DB_PORT', '3306')),
            database=os.environ.get('DB_NAME', 'coronary_atlas'),
            query={'charset': 'utf8mb4'})
    return create_engine(url, pool_pre_ping=True, pool_recycle=1800)


def initialize_database():
    Base.metadata.create_all(get_engine())


def get_db():
    db = Session(get_engine())
    try:
        yield db
    except SQLAlchemyError as error:
        db.rollback()
        raise HTTPException(503, 'The account database is unavailable. Please try again.') from error
    finally:
        db.close()
