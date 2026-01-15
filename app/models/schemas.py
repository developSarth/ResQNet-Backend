import pydantic
from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime, date
from enum import Enum

#Enums

class GovAuthorityLevel(str, Enum):
    HEAD = "head"
    AUTHORITY = "authority"
    OFFICER = "officer"

class GovAccountStatus(str, Enum):
    PENDING = "pending"
    VERIFIED = "verified"
    SUSPENDED = "suspended"
    REJECTED = "rejected"

class GovDocumentType(str, Enum):
    ID_CARD = "id_card"
    AUTHORIZATION_LETTER = "authorization_letter"
    APPOINTMENT_ORDER = "appointment_order"

class VerificationStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"

#----------------------------------------------------------
#AUTH SCHEMAS

class UserCreate(BaseModel):
    email: EmailStr
    full_name: str
    username: str
    password: str

class LoginUser(BaseModel):
    username: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: Optional[str] = None
    role: Optional[str] = None

class TokenData(BaseModel):
    username: Optional[str] = None
    role: Optional[str] = None

class UserResponse(BaseModel):
    id: str  # Changed from int to str for UUID
    email: EmailStr
    full_name: Optional[str] = None
    username: str
    is_active: bool
    is_verified: bool
    role: Optional[str] = None  # Made optional since new users may not have a role
    created_at: datetime

    class Config:
        from_attributes = True

class Location(BaseModel):
    latitude: float
    longitude: float

class CitizenProfile(BaseModel):
    user_id: int
    mobile_number: str
    alt_mobile_number: Optional[str]
    residence_address: str
    occupation: Optional[str]
    encrypted_gov_id_ref: Optional[str]  # reference, NOT raw ID


from uuid import UUID

class VolunteerProfile(BaseModel):
    user_id: int
    ngo_id: Optional[UUID]
    mobile_number: str
    residence_address: str
    verification_status: VerificationStatus

class NGO(BaseModel):
    name: str
    registration_number: str
    mca_number: Optional[str]
    certificates_12A_80G: Optional[str]
    formation_document_ref: str
    verified_by_gov_user: Optional[UUID]
    verification_status: VerificationStatus


class GovVerificationDocumentBase(BaseModel):
    document_type: GovDocumentType
    issued_by: str
    issued_date: date
    valid_till: Optional[date]

class GovVerificationDocumentCreate(GovVerificationDocumentBase):
    gov_user_id: UUID
    encrypted_file_path: str

class GovVerificationDocument(GovVerificationDocumentBase):
    id: UUID
    gov_user_id: UUID
    encrypted_file_path: str
    verification_status: VerificationStatus
    reviewed_by: Optional[UUID]
    reviewed_at: Optional[datetime]

    class Config:
        from_attributes = True

class GovAuthorityAccountBase(BaseModel):
    department: str
    jurisdiction: str
    designation: str
    official_email: EmailStr
    authority_level: GovAuthorityLevel

class GovAuthorityAccountCreate(GovAuthorityAccountBase):
    user_id: UUID

class GovVerificationDecision(BaseModel):
    gov_user_id: UUID
    decision: VerificationStatus
    remarks: Optional[str]

class GovJWTPayload(BaseModel):
    sub: UUID
    role: str = "gov"
    authority_level: GovAuthorityLevel
    department: str
    jurisdiction: str


class Agent(BaseModel):
    prompt_post: str
    prompt_response: str
    prompt_time: datetime

class IncidentReport(BaseModel):
    location: Location
    severity: str #dropdown
    terror_related_or_riot: bool
    approx_people_affected: int
    casualties: bool
    pic_url:str   #picture input function 

class IncidentReportToVolunteer(BaseModel):
    approx_people_affected: int
    location: Location
    types_of_aid_needed: str  # STT output General Aid (Medical, Food, Shelter, etc.)   

class IncidentReportToGov(BaseModel):
    incident_type: str
    danger_scale: int  # 1–5
    terror_related: bool                       #Done using "assist gov" button 
    location: Location
    financial_aid_estimate: Optional[str]
    incident_details: str




