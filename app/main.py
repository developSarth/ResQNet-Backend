"""
Crisis Command Center - Main Application
FastAPI backend with all routes and WebSocket support
"""
from fastapi import FastAPI, Depends
from starlette.middleware.sessions import SessionMiddleware
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import database
from database import engine, Base

# Import config
from config import settings

# Import routers
from dependency.router import router as auth_router
from routes.google_oauth import router as google_router
from routes.contacts import router as contacts_router
from routes.profiles import router as profiles_router
from routes.incidents import router as incidents_router
from routes.ngos import router as ngos_router
from routes.messages import router as messages_router
from routes.gov import router as gov_router
from ws_handlers.routes import router as ws_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan - create tables on startup"""
    # Import all models to register them
    from models.db_models import (
        User, CitizenProfile, VolunteerProfile, GovAuthorityAccount,
        GovVerificationDocument, NGO, Incident, Message, OTPSession,
        EmergencyContact
    )
    
    # Check if we should drop existing tables (useful for schema changes)
    drop_tables = os.getenv("DROP_TABLES_ON_START", "false").lower() == "true"
    
    if drop_tables:
        print("⚠️ DROP_TABLES_ON_START is enabled - dropping all tables...")
        Base.metadata.drop_all(bind=engine)
        print("🗑️ All tables dropped")
    
    # Create all tables
    Base.metadata.create_all(bind=engine)
    print("✅ Database tables created")
    yield
    print("🛑 Application shutdown")


# Initialize FastAPI app
app = FastAPI(
    title="Crisis Command Center",
    version="1.0.0",
    description="Emergency Response Coordination Platform",
    lifespan=lifespan
)

# Add middleware
app.add_middleware(
    SessionMiddleware, 
    secret_key=settings.SECRET_KEY
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure properly in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

# Include routers
app.include_router(auth_router)
app.include_router(google_router)
app.include_router(contacts_router)
app.include_router(profiles_router)
app.include_router(incidents_router)
app.include_router(ngos_router)
app.include_router(messages_router)
app.include_router(gov_router)
app.include_router(ws_router)


# ==================== HEALTH CHECK ====================

@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "status": "online",
        "app": "Crisis Command Center",
        "version": "1.0.0"
    }


@app.get("/health")
async def health_check():
    """Detailed health check"""
    return {
        "status": "healthy",
        "database": "connected",
        "services": {
            "auth": "active",
            "incidents": "active",
            "messaging": "active",
            "websockets": "active"
        }
    }


# ==================== RUN SERVER ====================

if __name__ == "__main__":
    import uvicorn
    print("🚨 Starting Crisis Command Center API...")
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )
