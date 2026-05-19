"""
database.py - Database Connection and Session Setup

This file sets up the SQLAlchemy engine, session factory, and declarative base
that the rest of the application uses to interact with the database.

Key objects exported:
  - engine:       The SQLAlchemy Engine that manages the actual database
                  connection pool.
  - SessionLocal: A factory (class) that creates new database sessions. Each
                  session represents a conversation with the database.
  - Base:         The declarative base class that all ORM models inherit from.
                  It keeps a registry of every model/table.
  - get_db():     A FastAPI dependency that provides a database session to route
                  handlers and automatically closes it when the request finishes.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from app.config import settings

# ---------------------------------------------------------------------------
# SQLite-specific workaround
# ---------------------------------------------------------------------------
# SQLite only allows one thread to use a connection at a time by default.
# Setting check_same_thread=False disables that check so FastAPI (which is
# multi-threaded) can reuse connections safely. This flag is ignored for
# other databases (e.g. PostgreSQL).
connect_args = {}
if settings.DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

# ---------------------------------------------------------------------------
# Create the SQLAlchemy engine
# ---------------------------------------------------------------------------
# The engine is the starting point for all database operations. It holds the
# connection pool and dialect information (SQLite, PostgreSQL, etc.).
engine = create_engine(settings.DATABASE_URL, connect_args=connect_args)

# ---------------------------------------------------------------------------
# Create a configured session factory
# ---------------------------------------------------------------------------
# SessionLocal is a class (not an instance). Calling SessionLocal() creates a
# new session. autocommit=False means we must explicitly call db.commit().
# autoflush=False prevents automatic SQL emission before queries, giving us
# more control over when writes happen.
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# ---------------------------------------------------------------------------
# Declarative base for ORM models
# ---------------------------------------------------------------------------
# All model classes (User, Course, Section, etc.) inherit from Base.
# Base.metadata holds information about every table and is used by
# create_all() to generate tables in the database.
Base = declarative_base()


def get_db():
    """
    FastAPI dependency that yields a database session.

    Usage in a route:
        @router.get("/items")
        def list_items(db: Session = Depends(get_db)):
            ...

    The `yield` makes this a generator-based dependency. FastAPI will:
      1. Call next() to get the session (before the route runs).
      2. Let the route use the session.
      3. After the route finishes (or raises an exception), execute the
         `finally` block to close the session and release the connection.
    """
    db = SessionLocal()
    try:
        yield db       # Provide the session to the route handler
    finally:
        db.close()     # Always close to return the connection to the pool
