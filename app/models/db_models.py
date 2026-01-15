"""
Crisis Command Center - SQLAlchemy Database Models
All tables with proper relationships and constraints
"""
from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime, Text, Float, 
    ForeignKey, Enum as SQLEnum, JSON, Date, LargeBinary
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base
import uuid
import enum

# ==================== ENUMS ====================

class UserRole(str, enum.Enum):
    CITIZEN = "citizen"
    VOLUNTEER = "volunteer"
    NGO = "ngo"
    GOV_HEAD = "gov_head"
    GOV_AUTHORITY = "gov_authority"
    GOV_OFFICER = "gov_officer"

class IncidentStatus(str, enum.Enum):
    REPORTED = "reported"
    ASSIGNED_NGO = "assigned_ngo"
    EMERGENCY_DISPATCHED = "emergency_dispatched"
    NGO_RESPONDING = "ngo_responding"
    ESCALATED_GOV = "escalated_gov"
    RESOLVED = "resolved"

class IncidentSeverity(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class VerificationStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"

class GovDocumentType(str, enum.Enum):
    ID_CARD = "id_card"
    AUTHORIZATION_LETTER = "authorization_letter"
    APPOINTMENT_ORDER = "appointment_order"

class GovAuthorityLevel(str, enum.Enum):
    HEAD = "head"
    AUTHORITY = "authority"
    OFFICER = "officer"

class MessageType(str, enum.Enum):
    INCIDENT_REPORT = "incident_report"
    UPDATE = "update"
    ESCALATION = "escalation"
    SYSTEM = "system"

# ==================== USER MODEL ====================

class User(Base):
    __tablename__ = "users"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, index=True, nullable=False)
    username = Column(String(100), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=True)  # Nullable for OAuth
    full_name = Column(String(255), nullable=True)
    mobile_number = Column(String(20), nullable=True)
    google_id = Column(String(255), nullable=True, unique=True)
    role = Column(SQLEnum(UserRole), default=UserRole.CITIZEN)
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    citizen_profile = relationship("CitizenProfile", back_populates="user", uselist=False)
    volunteer_profile = relationship("VolunteerProfile", back_populates="user", uselist=False)
    # Note: Other relationships (gov_account, incidents, messages) removed to simplify
    # Use direct queries instead: db.query(Incident).filter(Incident.reporter_id == user_id)

# ==================== PROFILE MODELS ====================

class CitizenProfile(Base):
    __tablename__ = "citizen_profiles"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    alt_mobile_number = Column(String(20), nullable=True)
    residence_address = Column(Text, nullable=False)
    city = Column(String(100), nullable=True)
    state = Column(String(100), nullable=True)
    pincode = Column(String(10), nullable=True)
    occupation = Column(String(100), nullable=True)
    encrypted_gov_id_ref = Column(LargeBinary, nullable=True)  # Encrypted government ID
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationship
    user = relationship("User", back_populates="citizen_profile")

class VolunteerProfile(Base):
    __tablename__ = "volunteer_profiles"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    ngo_id = Column(UUID(as_uuid=True), ForeignKey("ngos.id", ondelete="SET NULL"), nullable=True)
    residence_address = Column(Text, nullable=False)
    city = Column(String(100), nullable=True)
    state = Column(String(100), nullable=True)
    verification_status = Column(SQLEnum(VerificationStatus), default=VerificationStatus.PENDING)
    skills = Column(JSON, nullable=True)  # List of skills
    availability = Column(String(50), nullable=True)  # e.g., "weekends", "full-time"
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    user = relationship("User", back_populates="volunteer_profile")
    ngo = relationship("NGO", back_populates="volunteers")

class GovAuthorityAccount(Base):
    __tablename__ = "gov_authority_accounts"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    department = Column(String(255), nullable=False)
    jurisdiction = Column(String(255), nullable=False)
    designation = Column(String(255), nullable=False)
    official_email = Column(String(255), nullable=False)
    authority_level = Column(SQLEnum(GovAuthorityLevel), nullable=False)
    account_status = Column(SQLEnum(VerificationStatus), default=VerificationStatus.PENDING)
    verified_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    verified_at = Column(DateTime(timezone=True), nullable=True)
    rejection_remarks = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    user = relationship("User", foreign_keys=[user_id])
    verifier = relationship("User", foreign_keys=[verified_by])
    documents = relationship("GovVerificationDocument", back_populates="gov_account")

class GovVerificationDocument(Base):
    __tablename__ = "gov_verification_documents"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    gov_account_id = Column(UUID(as_uuid=True), ForeignKey("gov_authority_accounts.id", ondelete="CASCADE"), nullable=False)
    document_type = Column(SQLEnum(GovDocumentType), nullable=False)
    issued_by = Column(String(255), nullable=False)
    issued_date = Column(Date, nullable=False)
    valid_till = Column(Date, nullable=True)
    encrypted_file_path = Column(String(500), nullable=False)  # Encrypted path
    encrypted_file_key = Column(LargeBinary, nullable=True)  # Encryption key (HS256)
    verification_status = Column(SQLEnum(VerificationStatus), default=VerificationStatus.PENDING)
    reviewed_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    gov_account = relationship("GovAuthorityAccount", back_populates="documents")
    reviewer = relationship("User", foreign_keys=[reviewed_by])

# ==================== NGO MODEL ====================

class NGO(Base):
    __tablename__ = "ngos"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False, unique=True)
    registration_number = Column(String(100), nullable=False, unique=True)
    mca_number = Column(String(100), nullable=True)
    certificates_12A_80G = Column(String(100), nullable=True)
    formation_document_path = Column(String(500), nullable=True)
    address = Column(Text, nullable=True)
    city = Column(String(100), nullable=True)
    state = Column(String(100), nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    contact_email = Column(String(255), nullable=True)
    contact_phone = Column(String(20), nullable=True)
    member_count = Column(Integer, default=0)
    verified_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    verification_status = Column(SQLEnum(VerificationStatus), default=VerificationStatus.PENDING)
    verified_at = Column(DateTime(timezone=True), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    volunteers = relationship("VolunteerProfile", back_populates="ngo")
    assigned_incidents = relationship("Incident", back_populates="assigned_ngo")
    verifier = relationship("User", foreign_keys=[verified_by])

# ==================== INCIDENT MODEL ====================

class Incident(Base):
    __tablename__ = "incidents"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    reporter_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    incident_type = Column(String(100), nullable=False)  # fire, flood, medical, etc.
    severity = Column(SQLEnum(IncidentSeverity), nullable=False)
    status = Column(SQLEnum(IncidentStatus), default=IncidentStatus.REPORTED)
    
    # Location
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    address = Column(Text, nullable=True)
    city = Column(String(100), nullable=True)
    state = Column(String(100), nullable=True)
    
    # Details
    description = Column(Text, nullable=True)
    approx_people_affected = Column(Integer, default=0)
    casualties = Column(Boolean, default=False)
    terror_related = Column(Boolean, default=False)
    aid_needed = Column(Text, nullable=True)
    image_urls = Column(JSON, nullable=True)  # List of image URLs
    
    # Assignment
    assigned_ngo_id = Column(UUID(as_uuid=True), ForeignKey("ngos.id", ondelete="SET NULL"), nullable=True)
    assigned_at = Column(DateTime(timezone=True), nullable=True)
    
    # Escalation
    escalated_to_gov = Column(Boolean, default=False)
    escalation_reason = Column(Text, nullable=True)
    escalated_at = Column(DateTime(timezone=True), nullable=True)
    danger_scale = Column(Integer, nullable=True)  # 1-5
    financial_aid_estimate = Column(String(100), nullable=True)
    
    # Tracking
    emergency_dispatched_at = Column(DateTime(timezone=True), nullable=True)
    ngo_responded_at = Column(DateTime(timezone=True), nullable=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    resolution_notes = Column(Text, nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    reporter = relationship("User", foreign_keys=[reporter_id])
    assigned_ngo = relationship("NGO", back_populates="assigned_incidents")
    messages = relationship("Message", back_populates="incident")

# ==================== MESSAGE MODEL ====================

class Message(Base):
    __tablename__ = "messages"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    sender_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    receiver_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    incident_id = Column(UUID(as_uuid=True), ForeignKey("incidents.id", ondelete="CASCADE"), nullable=True)
    
    message_type = Column(SQLEnum(MessageType), default=MessageType.UPDATE)
    subject = Column(String(255), nullable=True)
    content = Column(Text, nullable=False)
    extra_data = Column(JSON, nullable=True)  # Additional data as JSON (renamed from 'metadata' which is reserved)
    
    is_read = Column(Boolean, default=False)
    read_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    sender = relationship("User", foreign_keys=[sender_id])
    receiver = relationship("User", foreign_keys=[receiver_id])
    incident = relationship("Incident", back_populates="messages")

# ==================== OTP SESSION MODEL ====================

class OTPSession(Base):
    __tablename__ = "otp_sessions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=True)
    mobile_number = Column(String(20), nullable=False)
    otp_hash = Column(String(255), nullable=False)  # Hashed OTP
    purpose = Column(String(50), nullable=False)  # "registration", "login", "verification"
    attempts = Column(Integer, default=0)
    is_verified = Column(Boolean, default=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationship
    user = relationship("User")

# ==================== EMERGENCY CONTACTS (Static Data) ====================

class EmergencyContact(Base):
    __tablename__ = "emergency_contacts"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    category = Column(String(50), nullable=False)  # police, ambulance, fire, national
    name = Column(String(255), nullable=False)
    phone_number = Column(String(50), nullable=False)
    alternate_number = Column(String(50), nullable=True)
    email = Column(String(255), nullable=True)
    state_code = Column(String(5), nullable=True)  # NULL for national contacts
    state_name = Column(String(100), nullable=True)
    is_national = Column(Boolean, default=False)
    priority = Column(Integer, default=0)  # Lower = higher priority
    created_at = Column(DateTime(timezone=True), server_default=func.now())
