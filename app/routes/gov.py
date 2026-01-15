"""
Crisis Command Center - Government Routes
Delegate verification, escalated incidents, official contacts
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
import uuid

from app.database import get_db
from app.models.db_models import (
    GovAuthorityAccount, GovVerificationDocument, User, Incident,
    VerificationStatus, UserRole, IncidentStatus, GovAuthorityLevel
)
from app.utils.encryption import document_encryption

router = APIRouter(prefix="/api/gov", tags=["Government"])


# ==================== SCHEMAS ====================

class VerificationDecision(BaseModel):
    gov_account_id: str
    decision: str  # "approved" or "rejected"
    remarks: Optional[str] = None


class PendingVerificationResponse(BaseModel):
    id: str
    user_id: str
    name: str
    email: str
    department: str
    jurisdiction: str
    designation: str
    authority_level: str
    submitted_at: datetime
    document_count: int

    class Config:
        from_attributes = True


# ==================== OFFICIAL CONTACTS ====================

OFFICIAL_CONTACTS = {
    "nsg": {
        "name": "National Security Guard (NSG)",
        "hq_control_room": "011-25671527",
        "emails": ["nsghq@nic.in", "dutyoffr@nsg.gov.in"],
        "description": "For terror-related emergencies and hostage situations"
    },
    "bsf": {
        "name": "Border Security Force (BSF)",
        "control_room": "011-24362361",
        "general": "011-24368925/26",
        "email": "edpdte@bsf.nic.in",
        "description": "Border security and critical area protection"
    },
    "ndrf": {
        "name": "National Disaster Response Force (NDRF)",
        "control_room": "011-26701700",
        "toll_free": "1070",
        "description": "Natural disasters and mass casualty events"
    },
    "mha": {
        "name": "Ministry of Home Affairs",
        "control_room": "011-23092923",
        "description": "Central coordination for national emergencies"
    }
}


# ==================== ENDPOINTS ====================

@router.get("/official-contacts")
async def get_official_contacts():
    """Get official national security and government contacts"""
    return OFFICIAL_CONTACTS


@router.get("/pending-verifications", response_model=List[PendingVerificationResponse])
async def get_pending_verifications(
    reviewer_id: str,
    db: Session = Depends(get_db)
):
    """Get pending government delegate verifications (for HEAD authority only)"""
    
    # Verify reviewer is HEAD authority
    reviewer = db.query(User).filter(User.id == reviewer_id).first()
    if not reviewer or reviewer.role != UserRole.GOV_HEAD:
        raise HTTPException(
            status_code=403,
            detail="Only HEAD authorities can review verifications"
        )
    
    # Get pending accounts
    pending_accounts = db.query(GovAuthorityAccount).filter(
        GovAuthorityAccount.account_status == VerificationStatus.PENDING
    ).all()
    
    result = []
    for account in pending_accounts:
        user = db.query(User).filter(User.id == account.user_id).first()
        doc_count = db.query(GovVerificationDocument).filter(
            GovVerificationDocument.gov_account_id == account.id
        ).count()
        
        if user:
            result.append(PendingVerificationResponse(
                id=str(account.id),
                user_id=str(account.user_id),
                name=user.full_name or user.username,
                email=account.official_email,
                department=account.department,
                jurisdiction=account.jurisdiction,
                designation=account.designation,
                authority_level=account.authority_level.value,
                submitted_at=account.created_at,
                document_count=doc_count
            ))
    
    return result


@router.get("/verification/{account_id}")
async def get_verification_details(
    account_id: str,
    reviewer_id: str,
    db: Session = Depends(get_db)
):
    """Get detailed verification info including documents"""
    
    # Verify reviewer is HEAD
    reviewer = db.query(User).filter(User.id == reviewer_id).first()
    if not reviewer or reviewer.role != UserRole.GOV_HEAD:
        raise HTTPException(status_code=403, detail="Unauthorized")
    
    account = db.query(GovAuthorityAccount).filter(
        GovAuthorityAccount.id == account_id
    ).first()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    
    user = db.query(User).filter(User.id == account.user_id).first()
    documents = db.query(GovVerificationDocument).filter(
        GovVerificationDocument.gov_account_id == account.id
    ).all()
    
    return {
        "account": {
            "id": str(account.id),
            "department": account.department,
            "jurisdiction": account.jurisdiction,
            "designation": account.designation,
            "official_email": account.official_email,
            "authority_level": account.authority_level.value,
            "status": account.account_status.value,
            "created_at": account.created_at.isoformat()
        },
        "user": {
            "id": str(user.id),
            "name": user.full_name,
            "email": user.email,
            "mobile": user.mobile_number
        } if user else None,
        "documents": [{
            "id": str(doc.id),
            "type": doc.document_type.value,
            "issued_by": doc.issued_by,
            "issued_date": doc.issued_date.isoformat(),
            "valid_till": doc.valid_till.isoformat() if doc.valid_till else None,
            "status": doc.verification_status.value
        } for doc in documents]
    }


@router.post("/verify")
async def verify_delegate(
    decision: VerificationDecision,
    reviewer_id: str,
    db: Session = Depends(get_db)
):
    """Approve or reject a government delegate registration"""
    
    # Verify reviewer is HEAD
    reviewer = db.query(User).filter(User.id == reviewer_id).first()
    if not reviewer or reviewer.role != UserRole.GOV_HEAD:
        raise HTTPException(status_code=403, detail="Only HEAD can verify delegates")
    
    # Get account
    account = db.query(GovAuthorityAccount).filter(
        GovAuthorityAccount.id == decision.gov_account_id
    ).first()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    
    # Map decision
    status_map = {
        "approved": VerificationStatus.APPROVED,
        "rejected": VerificationStatus.REJECTED
    }
    new_status = status_map.get(decision.decision.lower())
    if not new_status:
        raise HTTPException(status_code=400, detail="Invalid decision")
    
    # Update account
    account.account_status = new_status
    account.verified_by = uuid.UUID(reviewer_id)
    account.verified_at = datetime.utcnow()
    if decision.remarks:
        account.rejection_remarks = decision.remarks
    
    # Update user verification status
    user = db.query(User).filter(User.id == account.user_id).first()
    if user and new_status == VerificationStatus.APPROVED:
        user.is_verified = True
    
    # Update all documents status
    documents = db.query(GovVerificationDocument).filter(
        GovVerificationDocument.gov_account_id == account.id
    ).all()
    for doc in documents:
        doc.verification_status = new_status
        doc.reviewed_by = uuid.UUID(reviewer_id)
        doc.reviewed_at = datetime.utcnow()
    
    db.commit()
    
    return {
        "account_id": str(account.id),
        "status": new_status.value,
        "message": f"Account {decision.decision}"
    }


@router.get("/escalated-incidents")
async def get_escalated_incidents(
    gov_user_id: str,
    db: Session = Depends(get_db)
):
    """Get incidents escalated to government"""
    
    # Get gov account
    gov_account = db.query(GovAuthorityAccount).filter(
        GovAuthorityAccount.user_id == gov_user_id,
        GovAuthorityAccount.account_status == VerificationStatus.APPROVED
    ).first()
    
    if not gov_account:
        raise HTTPException(status_code=403, detail="Not a verified government authority")
    
    # Get escalated incidents in jurisdiction
    incidents = db.query(Incident).filter(
        Incident.escalated_to_gov == True,
        Incident.state.ilike(f"%{gov_account.jurisdiction}%")
    ).order_by(Incident.escalated_at.desc()).all()
    
    return [{
        "id": str(inc.id),
        "incident_type": inc.incident_type,
        "severity": inc.severity.value,
        "status": inc.status.value,
        "location": {
            "address": inc.address,
            "city": inc.city,
            "state": inc.state
        },
        "danger_scale": inc.danger_scale,
        "terror_related": inc.terror_related,
        "financial_aid_estimate": inc.financial_aid_estimate,
        "escalation_reason": inc.escalation_reason,
        "escalated_at": inc.escalated_at.isoformat() if inc.escalated_at else None,
        "people_affected": inc.approx_people_affected
    } for inc in incidents]


@router.get("/statistics")
async def get_dashboard_statistics(
    gov_user_id: str,
    db: Session = Depends(get_db)
):
    """Get dashboard statistics for government users"""
    
    gov_account = db.query(GovAuthorityAccount).filter(
        GovAuthorityAccount.user_id == gov_user_id
    ).first()
    
    if not gov_account:
        raise HTTPException(status_code=403, detail="Not a government authority")
    
    # Count incidents by status
    total_incidents = db.query(Incident).filter(
        Incident.state.ilike(f"%{gov_account.jurisdiction}%")
    ).count()
    
    escalated = db.query(Incident).filter(
        Incident.state.ilike(f"%{gov_account.jurisdiction}%"),
        Incident.escalated_to_gov == True
    ).count()
    
    resolved = db.query(Incident).filter(
        Incident.state.ilike(f"%{gov_account.jurisdiction}%"),
        Incident.status == IncidentStatus.RESOLVED
    ).count()
    
    pending_verifications = 0
    if gov_account.authority_level == GovAuthorityLevel.HEAD:
        pending_verifications = db.query(GovAuthorityAccount).filter(
            GovAuthorityAccount.account_status == VerificationStatus.PENDING
        ).count()
    
    return {
        "total_incidents": total_incidents,
        "escalated_incidents": escalated,
        "resolved_incidents": resolved,
        "pending_verifications": pending_verifications,
        "jurisdiction": gov_account.jurisdiction
    }
