"""
Authentication Service
======================
This module provides the core authentication utilities used across the
application. It handles three responsibilities:

  1. Password hashing and verification using bcrypt.
  2. JWT (JSON Web Token) creation for session management.
  3. Extracting and validating the current user from an incoming request's
     Authorization header (Bearer token).

The JWT flow works as follows:
  - When a user logs in or registers, create_access_token() generates a
    signed JWT containing the user's ID and an expiration time.
  - On every subsequent API request, the frontend sends this token in the
    "Authorization: Bearer <token>" header.
  - get_current_user() decodes the token, extracts the user ID, and
    fetches the corresponding User record from the database.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from app.config import settings
from app.database import get_db
from app.models.models import User

# Configure the password hashing context to use bcrypt.
# "deprecated='auto'" means any older hash schemes will be auto-upgraded on verify.
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# OAuth2PasswordBearer tells FastAPI where the login endpoint is located.
# It automatically extracts the Bearer token from the Authorization header.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Compare a plaintext password against a bcrypt hash.

    Uses passlib's verify method which handles the salt extraction and
    hash comparison internally. Returns True if the password matches.
    """
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """
    Hash a plaintext password using bcrypt.

    The resulting hash includes a randomly generated salt, so hashing
    the same password twice produces different outputs. This is the value
    that gets stored in the database (never the plaintext password).
    """
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Create a signed JWT access token.

    Args:
        data: Dictionary of claims to embed in the token. Typically
              {"sub": "<user_id>"} where "sub" is the JWT subject claim.
        expires_delta: How long until the token expires. If not provided,
                       defaults to the ACCESS_TOKEN_EXPIRE_MINUTES setting.

    Returns:
        A signed JWT string that the client stores and sends with
        every subsequent request.
    """
    to_encode = data.copy()
    # Calculate the expiration timestamp (current UTC time + delta)
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    # Sign the token with the application's secret key using the configured algorithm (e.g., HS256)
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    """
    FastAPI dependency that extracts and validates the current user from a JWT.

    This function is used as a dependency in route handlers like:
        current_user: User = Depends(get_current_user)

    Steps:
      1. Decode the JWT token using the application's secret key.
      2. Extract the user ID from the "sub" (subject) claim.
      3. Query the database for the corresponding User record.
      4. If any step fails (invalid token, expired token, user not found),
         raise a 401 Unauthorized error.

    Returns:
        The authenticated User ORM object.
    """
    # Prepare the error response in advance for any authentication failure
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},  # Required by OAuth2 spec
    )
    try:
        # Decode and verify the JWT signature and expiration
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        # Extract the "sub" claim which holds the user's database ID
        user_id_raw = payload.get("sub")
        if user_id_raw is None:
            raise credentials_exception
        user_id = int(user_id_raw)
    except (JWTError, ValueError):
        # JWTError: invalid/expired token; ValueError: "sub" is not a valid integer
        raise credentials_exception
    # Fetch the user from the database by their ID
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise credentials_exception
    return user
