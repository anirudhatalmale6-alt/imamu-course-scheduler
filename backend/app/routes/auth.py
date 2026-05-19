"""
Authentication API Routes
=========================
This file defines the REST API endpoints for user authentication.
It handles three operations:
  1. POST /api/auth/register - Create a new user account and return a JWT token.
  2. POST /api/auth/login    - Authenticate an existing user and return a JWT token.
  3. GET  /api/auth/me       - Retrieve the profile of the currently logged-in user.

Each endpoint interacts with the database through SQLAlchemy and delegates
password hashing / JWT creation to the auth service layer.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.models import User, UserRole
from app.schemas import UserCreate, UserLogin, UserResponse, TokenResponse
from app.services.auth import get_password_hash, verify_password, create_access_token, get_current_user

# Create a router for all authentication endpoints, grouped under the "/api/auth" prefix.
# The "tags" parameter groups these endpoints together in the auto-generated API docs.
router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse)
def register(user_data: UserCreate, db: Session = Depends(get_db)):
    """
    Register a new user account.

    Steps:
      1. Check that the chosen username is not already taken.
      2. Check that the email address is not already in use.
      3. Create a new User record with a bcrypt-hashed password.
      4. Persist the user to the database.
      5. Generate a JWT access token so the user is logged in immediately.

    Returns a TokenResponse containing the JWT token and the user's profile.
    """
    # Ensure username uniqueness
    if db.query(User).filter(User.username == user_data.username).first():
        raise HTTPException(status_code=400, detail="Username already taken")
    # Ensure email uniqueness
    if db.query(User).filter(User.email == user_data.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")

    # Build the new user object with a hashed (not plaintext) password
    user = User(
        username=user_data.username,
        email=user_data.email,
        hashed_password=get_password_hash(user_data.password),
        full_name=user_data.full_name,
        role=UserRole(user_data.role),
        gender=user_data.gender,
        department=user_data.department,
        level=user_data.level,
    )
    db.add(user)       # Stage the new user for insertion
    db.commit()        # Write to the database
    db.refresh(user)   # Reload the user so auto-generated fields (like id) are populated

    # Issue a JWT token with the user's ID embedded in the "sub" (subject) claim
    token = create_access_token(data={"sub": str(user.id)})
    return TokenResponse(
        access_token=token,
        user=UserResponse.model_validate(user),
    )


@router.post("/login", response_model=TokenResponse)
def login(login_data: UserLogin, db: Session = Depends(get_db)):
    """
    Authenticate an existing user with username and password.

    Steps:
      1. Look up the user by username.
      2. Verify the supplied password against the stored bcrypt hash.
      3. If valid, generate and return a JWT access token.

    Returns a TokenResponse containing the JWT token and the user's profile.
    Raises 401 if the username does not exist or the password is wrong.
    """
    # Look up user by username
    user = db.query(User).filter(User.username == login_data.username).first()
    # Reject if user not found OR password hash does not match
    if not user or not verify_password(login_data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid username or password")

    # Generate a JWT token for the authenticated session
    token = create_access_token(data={"sub": str(user.id)})
    return TokenResponse(
        access_token=token,
        user=UserResponse.model_validate(user),
    )


@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    """
    Return the profile of the currently authenticated user.

    The `get_current_user` dependency extracts and validates the JWT token
    from the Authorization header, then fetches the corresponding User from
    the database. This endpoint simply serializes that user into a response.
    """
    return UserResponse.model_validate(current_user)
