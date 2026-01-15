from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import timedelta

from app.database import get_db
from app.auth.models import User
from app.models.schemas import UserCreate, UserResponse, Token
from app.schemas.utils import (
    hash_password, 
    verify_password, 
    create_access_token,
    ACCESS_TOKEN_EXPIRE_MINUTES
)
from app.auth.oauth2 import get_current_user

router = APIRouter(prefix="/auth", tags=["Authentication"])

# ========== REGISTRATION ==========

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(user_data: UserCreate, db: Session = Depends(get_db)):
    """Register a new user with email and password"""
    
    # Check if email already exists
    existing_email = db.query(User).filter(User.email == user_data.email).first()
    if existing_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Check if username already exists
    existing_username = db.query(User).filter(User.username == user_data.username).first()
    if existing_username:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already taken"
        )
    
    # Create new user
    new_user = User(
        email=user_data.email,
        username=user_data.username,
        hashed_password=hash_password(user_data.password),
        full_name=user_data.full_name
    )
    
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    # Return UserResponse with properly serialized fields
    return UserResponse(
        id=str(new_user.id),
        email=new_user.email,
        full_name=new_user.full_name,
        username=new_user.username,
        is_active=new_user.is_active,
        is_verified=new_user.is_verified,
        role=new_user.role.value if new_user.role else None,
        created_at=new_user.created_at
    )

# ========== LOGIN (Form-based for OAuth2PasswordBearer) ==========

@router.post("/login", response_model=Token)
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    """
    Login with email/password.
    Uses OAuth2PasswordRequestForm for Swagger UI compatibility.
    'username' field contains the email.
    """
    
    # Find user by email
    user = db.query(User).filter(User.email == form_data.username).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Check if user has a password (OAuth users might not)
    if not user.hashed_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Please login with your OAuth provider (Google)"
        )
    
    # Verify password
    if not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Create access token
    access_token = create_access_token(
        data={"user_id": str(user.id), "email": user.email},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    
    # Get user role
    user_role = user.role.value if hasattr(user, 'role') and user.role else None
    
    return {
        "access_token": access_token, 
        "token_type": "bearer",
        "user_id": str(user.id),
        "role": user_role
    }

# ========== GET CURRENT USER ==========

@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    """Get current authenticated user's profile"""
    return UserResponse(
        id=str(current_user.id),
        email=current_user.email,
        full_name=current_user.full_name,
        username=current_user.username,
        is_active=current_user.is_active,
        is_verified=current_user.is_verified,
        role=current_user.role.value if current_user.role else None,
        created_at=current_user.created_at
    )

# ========== PROTECTED ROUTE EXAMPLE ==========

@router.get("/protected")
def protected_route(current_user: User = Depends(get_current_user)):
    """Example of a protected route"""
    return {
        "message": f"Hello {current_user.email}! This is a protected route.",
        "user_id": current_user.id
    }