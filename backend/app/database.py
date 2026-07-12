"""Shared database foundation for the AssetFlow backend.

This is the single seam that every self-contained module consumes through its
local ``deps.py`` (``from app.database import Base, get_db``). Providing it here
unifies every module onto **one** declarative ``Base`` / metadata and **one**
SQLite (or Postgres) session, so cross-module readers (Dashboard, Reports) and
the string-FK ``assets`` contract all resolve against the same database.
"""
from __future__ import annotations

import os
from typing import Iterator

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker

# Load environment variables
load_dotenv()

# Database URL configuration
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "sqlite:///./assetflow.db"
)

# Convert relative SQLite path to absolute path relative to backend root
if DATABASE_URL.startswith("sqlite:///./"):
    db_name = DATABASE_URL.replace("sqlite:///./", "")
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    DATABASE_URL = f"sqlite:///{os.path.join(BASE_DIR, db_name)}"

# Connection arguments for SQLite
connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    connect_args["check_same_thread"] = False

# Create engine
engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    future=True
)

# Session factory
SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    future=True
)

# The one declarative base shared by every module's ORM models.
Base = declarative_base()


def get_db() -> Iterator[Session]:
    """Yield a request-scoped session that is always closed.

    This is the production ``get_db`` that every module's ``deps.py`` imports.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
