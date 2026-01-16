from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from authlib.integrations.starlette_client import OAuth
from starlette.config import Config
from datetime import timedelta
import os
from dotenv import load_dotenv

from database import get_db
from auth.models import User
from schemas.utils import create_access_token, ACCESS_TOKEN_EXPIRE_MINUTES

load_dotenv()

router = APIRouter(prefix="/auth/google", tags=["Google OAuth"])

# ========== OAUTH CONFIGURATION ==========

config = Config(environ={
    "GOOGLE_CLIENT_ID": os.getenv("GOOGLE_CLIENT_ID"),
    "GOOGLE_CLIENT_SECRET": os.getenv("GOOGLE_CLIENT_SECRET"),
})

oauth = OAuth(config)

oauth.register(
    name='google',
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={
        'scope': 'openid email profile'
    }
)

# ========== GOOGLE LOGIN REDIRECT ==========

@router.get("/login")
async def google_login(request: Request):
    """
    Redirects user to Google's OAuth consent screen.
    After consent, Google redirects back to /auth/google/callback
    """
    redirect_uri = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:8000/auth/google/callback")
    return await oauth.google.authorize_redirect(request, redirect_uri)

# ========== GOOGLE CALLBACK ==========

@router.get("/callback")
async def google_callback(request: Request, db: Session = Depends(get_db)):
    """
    Handles the callback from Google after user consent.
    Creates/updates user and returns JWT token.
    """
    try:
        # Get the token from Google
        token = await oauth.google.authorize_access_token(request)
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Could not validate Google credentials: {str(e)}"
        )
    
    # Get user info from Google
    user_info = token.get('userinfo')
    
    if not user_info:
        raise HTTPException(
            status_code=400,
            detail="Could not get user info from Google"
        )
    
    email = user_info.get('email')
    google_id = user_info.get('sub')  # Google's unique user ID
    full_name = user_info.get('name')
    
    # Check if user exists
    user = db.query(User).filter(User.email == email).first()
    
    if user:
        # Update existing user's OAuth info if not set
        if not user.google_id:
            user.google_id = google_id
            user.is_verified = True  # Email verified by Google
            db.commit()
    else:
        # Create new user
        user = User(
            email=email,
            full_name=full_name,
            username=email.split('@')[0],  # Generate username from email
            google_id=google_id,
            is_verified=True,  # Google verifies emails
            is_active=True
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    
    # Create JWT token
    access_token = create_access_token(
        data={"user_id": user.id, "email": user.email},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    
    # Option 1: Return JSON (for API clients)
    # return {"access_token": access_token, "token_type": "bearer", "user": user}
    
    # Option 2: Redirect to frontend with token (for web apps)
    frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000")
    return RedirectResponse(url=f"{frontend_url}/auth/callback?token={access_token}")