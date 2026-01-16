"""
Crisis Command Center - Profile Registration Routes
Citizen, Volunteer, and Government profile registration with 2FA
"""
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import date
import uuid
import os

from database import get_db
from models.db_models import (
    User, CitizenProfile, VolunteerProfile, GovAuthorityAccount,
    GovVerificationDocument, NGO, UserRole, VerificationStatus,
    GovAuthorityLevel, GovDocumentType
)
from utils.encryption import encrypt_gov_id, document_encryption, hs256_signer
from utils.otp_service import otp_service
from config import settings

router = APIRouter(prefix="/api/profiles", tags=["Profiles"])


# ==================== REQUEST SCHEMAS ====================

class CitizenProfileCreate(BaseModel):
    mobile_number: str
    alt_mobile_number: Optional[str] = None
    residence_address: str
    city: Optional[str] = None
    state: Optional[str] = None
    pincode: Optional[str] = None
    occupation: Optional[str] = None
    gov_id_ref: Optional[str] = None  # Will be encrypted


class VolunteerProfileCreate(BaseModel):
    mobile_number: str
    residence_address: str
    city: Optional[str] = None
    state: Optional[str] = None
    ngo_id: Optional[str] = None  # UUID of existing NGO
    skills: Optional[List[str]] = None
    availability: Optional[str] = None


class NGOCreate(BaseModel):
    name: str
    registration_number: str
    mca_number: Optional[str] = None
    certificates_12A_80G: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None


class GovProfileCreate(BaseModel):
    mobile_number: str
    department: str
    jurisdiction: str
    designation: str
    official_email: EmailStr
    authority_level: str  # "head", "authority", "officer"


class GovDocumentCreate(BaseModel):
    document_type: str  # "id_card", "authorization_letter", "appointment_order"
    issued_by: str
    issued_date: date
    valid_till: Optional[date] = None


class OTPRequest(BaseModel):
    mobile_number: str
    purpose: str = "registration"


class OTPVerify(BaseModel):
    mobile_number: str
    otp: str
    purpose: str = "registration"


# ==================== RESPONSE SCHEMAS ====================

class ProfileResponse(BaseModel):
    id: str
    user_id: str
    status: str
    message: str

    class Config:
        from_attributes = True


# ==================== HELPER FUNCTIONS ====================

def get_current_user_from_token(token: str, db: Session) -> User:
    """Extract and validate user from JWT token"""
    from jose import jwt, JWTError
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id = payload.get("user_id")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token")
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        return user
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")


# ==================== OTP ENDPOINTS ====================

@router.post("/otp/send")
async def send_otp(request: OTPRequest):
    """Send OTP for 2FA verification (Gov/NGO registration)"""
    success, message = otp_service.send_otp(request.mobile_number, request.purpose)
    if success:
        return {"status": "success", "message": message}
    else:
        raise HTTPException(status_code=400, detail=message)


@router.post("/otp/verify")
async def verify_otp(request: OTPVerify):
    """Verify OTP for 2FA"""
    success, message = otp_service.verify_otp(
        request.mobile_number, 
        request.otp, 
        request.purpose
    )
    if success:
        return {"status": "success", "message": message, "verified": True}
    else:
        raise HTTPException(status_code=400, detail=message)


# ==================== CITIZEN PROFILE ====================

@router.post("/citizen", response_model=ProfileResponse)
async def create_citizen_profile(
    profile_data: CitizenProfileCreate,
    user_id: str,  # From frontend after login
    db: Session = Depends(get_db)
):
    """Complete citizen profile registration"""
    
    # Check user exists
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Check if profile already exists
    existing = db.query(CitizenProfile).filter(CitizenProfile.user_id == user_id).first()
    if existing:
        raise HTTPException(status_code=400, detail="Profile already exists")
    
    # Encrypt government ID if provided
    encrypted_gov_id = None
    if profile_data.gov_id_ref:
        encrypted_gov_id = encrypt_gov_id(profile_data.gov_id_ref)
    
    # Create profile
    profile = CitizenProfile(
        user_id=uuid.UUID(user_id),
        alt_mobile_number=profile_data.alt_mobile_number,
        residence_address=profile_data.residence_address,
        city=profile_data.city,
        state=profile_data.state,
        pincode=profile_data.pincode,
        occupation=profile_data.occupation,
        encrypted_gov_id_ref=encrypted_gov_id
    )
    
    # Update user
    user.mobile_number = profile_data.mobile_number
    user.role = UserRole.CITIZEN
    user.is_verified = True
    
    db.add(profile)
    db.commit()
    db.refresh(profile)
    
    return ProfileResponse(
        id=str(profile.id),
        user_id=str(profile.user_id),
        status="success",
        message="Citizen profile created successfully"
    )


# ==================== VOLUNTEER PROFILE ====================

@router.post("/volunteer", response_model=ProfileResponse)
async def create_volunteer_profile(
    profile_data: VolunteerProfileCreate,
    user_id: str,
    otp_verified: bool = False,  # Should be verified via /otp/verify first
    db: Session = Depends(get_db)
):
    """Complete volunteer profile registration (requires 2FA)"""
    
    if not otp_verified:
        raise HTTPException(
            status_code=400, 
            detail="OTP verification required. Use /api/profiles/otp/send first"
        )
    
    # Check user exists
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Check if profile already exists
    existing = db.query(VolunteerProfile).filter(VolunteerProfile.user_id == user_id).first()
    if existing:
        raise HTTPException(status_code=400, detail="Profile already exists")
    
    # Create profile
    profile = VolunteerProfile(
        user_id=uuid.UUID(user_id),
        ngo_id=uuid.UUID(profile_data.ngo_id) if profile_data.ngo_id else None,
        residence_address=profile_data.residence_address,
        city=profile_data.city,
        state=profile_data.state,
        skills=profile_data.skills,
        availability=profile_data.availability,
        verification_status=VerificationStatus.PENDING
    )
    
    # Update user
    user.mobile_number = profile_data.mobile_number
    user.role = UserRole.VOLUNTEER
    
    db.add(profile)
    db.commit()
    db.refresh(profile)
    
    return ProfileResponse(
        id=str(profile.id),
        user_id=str(profile.user_id),
        status="pending",
        message="Volunteer profile created. Awaiting verification."
    )


# ==================== NGO REGISTRATION ====================

@router.post("/ngo")
async def register_ngo(
    ngo_data: NGOCreate,
    user_id: str,
    otp_verified: bool = False,
    db: Session = Depends(get_db)
):
    """Register a new NGO (requires 2FA)"""
    
    if not otp_verified:
        raise HTTPException(
            status_code=400,
            detail="OTP verification required"
        )
    
    # Check if NGO already exists
    existing = db.query(NGO).filter(
        (NGO.registration_number == ngo_data.registration_number) |
        (NGO.name == ngo_data.name)
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="NGO already registered")
    
    # Create NGO
    ngo = NGO(
        name=ngo_data.name,
        registration_number=ngo_data.registration_number,
        mca_number=ngo_data.mca_number,
        certificates_12A_80G=ngo_data.certificates_12A_80G,
        address=ngo_data.address,
        city=ngo_data.city,
        state=ngo_data.state,
        latitude=ngo_data.latitude,
        longitude=ngo_data.longitude,
        contact_email=ngo_data.contact_email,
        contact_phone=ngo_data.contact_phone,
        verification_status=VerificationStatus.PENDING
    )
    
    db.add(ngo)
    db.commit()
    db.refresh(ngo)
    
    return {
        "id": str(ngo.id),
        "name": ngo.name,
        "status": "pending",
        "message": "NGO registered. Awaiting government verification."
    }


# ==================== GOVERNMENT PROFILE ====================

@router.post("/gov", response_model=ProfileResponse)
async def create_gov_profile(
    profile_data: GovProfileCreate,
    user_id: str,
    otp_verified: bool = False,
    db: Session = Depends(get_db)
):
    """Create government authority profile (requires 2FA)"""
    
    if not otp_verified:
        raise HTTPException(
            status_code=400,
            detail="OTP verification required for government registration"
        )
    
    # Check user exists
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Check if profile already exists
    existing = db.query(GovAuthorityAccount).filter(GovAuthorityAccount.user_id == user_id).first()
    if existing:
        raise HTTPException(status_code=400, detail="Government profile already exists")
    
    # Map authority level
    level_map = {
        "head": GovAuthorityLevel.HEAD,
        "authority": GovAuthorityLevel.AUTHORITY,
        "officer": GovAuthorityLevel.OFFICER
    }
    authority_level = level_map.get(profile_data.authority_level.lower())
    if not authority_level:
        raise HTTPException(status_code=400, detail="Invalid authority level")
    
    # Determine user role based on authority level
    role_map = {
        GovAuthorityLevel.HEAD: UserRole.GOV_HEAD,
        GovAuthorityLevel.AUTHORITY: UserRole.GOV_AUTHORITY,
        GovAuthorityLevel.OFFICER: UserRole.GOV_OFFICER
    }
    
    # Create profile
    profile = GovAuthorityAccount(
        user_id=uuid.UUID(user_id),
        department=profile_data.department,
        jurisdiction=profile_data.jurisdiction,
        designation=profile_data.designation,
        official_email=profile_data.official_email,
        authority_level=authority_level,
        account_status=VerificationStatus.PENDING
    )
    
    # Update user
    user.mobile_number = profile_data.mobile_number
    user.role = role_map[authority_level]
    
    db.add(profile)
    db.commit()
    db.refresh(profile)
    
    return ProfileResponse(
        id=str(profile.id),
        user_id=str(profile.user_id),
        status="pending",
        message="Government profile submitted. Awaiting verification by higher authority."
    )


@router.post("/gov/document")
async def upload_gov_document(
    gov_account_id: str = Form(...),
    document_type: str = Form(...),
    issued_by: str = Form(...),
    issued_date: str = Form(...),
    valid_till: Optional[str] = Form(None),
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """Upload and encrypt government verification document"""
    
    # Validate gov account exists
    gov_account = db.query(GovAuthorityAccount).filter(
        GovAuthorityAccount.id == gov_account_id
    ).first()
    if not gov_account:
        raise HTTPException(status_code=404, detail="Government account not found")
    
    # Read file content
    file_content = await file.read()
    
    # Encrypt file content
    encrypted_content, salt = document_encryption.encrypt(file_content)
    
    # Save encrypted file
    upload_dir = os.path.join(settings.UPLOAD_DIR, "gov_docs")
    os.makedirs(upload_dir, exist_ok=True)
    file_id = str(uuid.uuid4())
    file_path = os.path.join(upload_dir, f"{file_id}.enc")
    
    with open(file_path, 'wb') as f:
        f.write(encrypted_content)
    
    # Sign document metadata
    signature = hs256_signer.sign_document_metadata(file_id, document_type, issued_by)
    
    # Map document type
    doc_type_map = {
        "id_card": GovDocumentType.ID_CARD,
        "authorization_letter": GovDocumentType.AUTHORIZATION_LETTER,
        "appointment_order": GovDocumentType.APPOINTMENT_ORDER
    }
    doc_type = doc_type_map.get(document_type.lower())
    if not doc_type:
        raise HTTPException(status_code=400, detail="Invalid document type")
    
    # Parse dates
    from datetime import datetime
    issued = datetime.strptime(issued_date, "%Y-%m-%d").date()
    valid = datetime.strptime(valid_till, "%Y-%m-%d").date() if valid_till else None
    
    # Create document record
    document = GovVerificationDocument(
        gov_account_id=uuid.UUID(gov_account_id),
        document_type=doc_type,
        issued_by=issued_by,
        issued_date=issued,
        valid_till=valid,
        encrypted_file_path=file_path,
        encrypted_file_key=salt,  # Store salt for decryption
        verification_status=VerificationStatus.PENDING
    )
    
    db.add(document)
    db.commit()
    db.refresh(document)
    
    return {
        "document_id": str(document.id),
        "signature": signature,
        "status": "uploaded",
        "message": "Document encrypted and uploaded successfully"
    }


# ==================== GET PROFILE ====================

@router.get("/me")
async def get_my_profile(user_id: str, db: Session = Depends(get_db)):
    """Get current user's profile based on role"""
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    profile_data = {
        "user": {
            "id": str(user.id),
            "email": user.email,
            "username": user.username,
            "full_name": user.full_name,
            "mobile_number": user.mobile_number,
            "role": user.role.value if user.role else None,
            "is_verified": user.is_verified
        }
    }
    
    # Get role-specific profile
    if user.role == UserRole.CITIZEN:
        citizen = db.query(CitizenProfile).filter(CitizenProfile.user_id == user.id).first()
        if citizen:
            profile_data["profile"] = {
                "residence_address": citizen.residence_address,
                "city": citizen.city,
                "state": citizen.state,
                "occupation": citizen.occupation
            }
    
    elif user.role == UserRole.VOLUNTEER:
        volunteer = db.query(VolunteerProfile).filter(VolunteerProfile.user_id == user.id).first()
        if volunteer:
            profile_data["profile"] = {
                "residence_address": volunteer.residence_address,
                "city": volunteer.city,
                "state": volunteer.state,
                "ngo_id": str(volunteer.ngo_id) if volunteer.ngo_id else None,
                "verification_status": volunteer.verification_status.value
            }
    
    elif user.role in [UserRole.GOV_HEAD, UserRole.GOV_AUTHORITY, UserRole.GOV_OFFICER]:
        gov = db.query(GovAuthorityAccount).filter(GovAuthorityAccount.user_id == user.id).first()
        if gov:
            profile_data["profile"] = {
                "department": gov.department,
                "jurisdiction": gov.jurisdiction,
                "designation": gov.designation,
                "authority_level": gov.authority_level.value,
                "account_status": gov.account_status.value
            }
    
    return profile_data
