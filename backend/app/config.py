"""
config.py - Application Configuration Settings

This file centralises every configurable value the application needs (database
URL, JWT secret, token lifetime, etc.) into a single Pydantic Settings class.
Values are read from environment variables when available; otherwise sensible
defaults are used.

Using a Settings class makes the app easy to reconfigure for different
environments (development, testing, production) without changing code - just
set the appropriate environment variables.
"""

import os
from pydantic_settings import BaseSettings

# Compute the project root directory (one level above the app/ package).
# This is used to build the default SQLite database path.
_base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class Settings(BaseSettings):
    """
    Central configuration for the Course Scheduler backend.

    Each attribute corresponds to a setting that can be overridden via an
    environment variable of the same name (e.g. export DATABASE_URL=...).

    Attributes:
        DATABASE_URL: Connection string for the database. Defaults to a local
            SQLite file named course_scheduler.db in the project root.
        SECRET_KEY: Secret used to sign JWT (JSON Web Token) access tokens.
            MUST be changed to a strong random value in production.
        ALGORITHM: The hashing algorithm used for JWT encoding/decoding (HS256).
        ACCESS_TOKEN_EXPIRE_MINUTES: How long an access token stays valid, in
            minutes. Default is 1440 (= 24 hours).
        UNIVERSITY_XML: Filename (or path) of the XML file containing seed
            data for departments, courses, instructors, rooms, and time slots.
    """
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        f"sqlite:///{os.path.join(_base_dir, 'course_scheduler.db')}"
    )
    SECRET_KEY: str = os.getenv("SECRET_KEY", "imamu-course-scheduler-secret-key-change-in-production")
    ALGORITHM: str = "HS256"                    # JWT signing algorithm
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440     # 24 hours
    UNIVERSITY_XML: str = os.getenv("UNIVERSITY_XML", "university.xml")


# Create a single shared instance so other modules can simply import `settings`
settings = Settings()
