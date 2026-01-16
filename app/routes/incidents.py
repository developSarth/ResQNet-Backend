"""
Crisis Command Center - Incident Routes
Incident reporting, tracking, assignment, and escalation
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
import uuid
import httpx

from database import get_db
from models.db_models import (
    Incident, User, NGO, Message, IncidentStatus, IncidentSeverity, 
    MessageType, UserRole
)
from config import settings

router = APIRouter(prefix="/api/incidents", tags=["Incidents"])


# ==================== REQUEST SCHEMAS ====================

class LocationInput(BaseModel):
    latitude: float
    longitude: float


class IncidentCreate(BaseModel):
    incident_type: str
    severity: str  # "low", "medium", "high", "critical"
    latitude: float
    longitude: float
    description: Optional[str] = None
    approx_people_affected: int = 0
    casualties: bool = False
    terror_related: bool = False
    aid_needed: Optional[str] = None
    image_urls: Optional[List[str]] = None


class IncidentAssign(BaseModel):
    ngo_id: str


class IncidentEscalate(BaseModel):
    danger_scale: int  # 1-5
    terror_related: bool
    financial_aid_estimate: Optional[str] = None
    incident_details: str


class IncidentStatusUpdate(BaseModel):
    status: str
    notes: Optional[str] = None


class MessageCreate(BaseModel):
    incident_id: str
    receiver_id: str
    subject: Optional[str] = None
    content: str


# ==================== RESPONSE SCHEMAS ====================

class IncidentResponse(BaseModel):
    id: str
    incident_type: str
    severity: str
    status: str
    address: Optional[str]
    city: Optional[str]
    state: Optional[str]
    created_at: datetime
    
    class Config:
        from_attributes = True


class TrackingResponse(BaseModel):
    incident_id: str
    status: str
    progress_percentage: int
    stages: List[dict]
    current_stage: int
    nearby_facilities: Optional[List[dict]] = None


# ==================== HELPER FUNCTIONS ====================

async def reverse_geocode(lat: float, lng: float) -> dict:
    """Convert latitude/longitude to address using Nominatim"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://nominatim.openstreetmap.org/reverse",
                params={
                    "lat": lat,
                    "lon": lng,
                    "format": "json",
                    "addressdetails": 1
                },
                headers={"User-Agent": settings.NOMINATIM_USER_AGENT}
            )
            if response.status_code == 200:
                data = response.json()
                address = data.get("address", {})
                return {
                    "display_name": data.get("display_name", ""),
                    "city": address.get("city") or address.get("town") or address.get("village", ""),
                    "state": address.get("state", ""),
                    "district": address.get("state_district", ""),
                    "country": address.get("country", ""),
                    "postcode": address.get("postcode", "")
                }
    except Exception as e:
        print(f"Geocoding error: {e}")
    return {"display_name": "", "city": "", "state": ""}


async def get_nearby_facilities(lat: float, lng: float) -> List[dict]:
    """Get nearby emergency facilities using Overpass API (OpenStreetMap)"""
    facilities = []
    
    # Query for hospitals, police, fire stations within 5km
    overpass_query = f"""
    [out:json][timeout:10];
    (
      node["amenity"="hospital"](around:5000,{lat},{lng});
      node["amenity"="police"](around:5000,{lat},{lng});
      node["amenity"="fire_station"](around:5000,{lat},{lng});
    );
    out body 20;
    """
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://overpass-api.de/api/interpreter",
                data={"data": overpass_query},
                timeout=15
            )
            if response.status_code == 200:
                data = response.json()
                for element in data.get("elements", []):
                    tags = element.get("tags", {})
                    facilities.append({
                        "type": tags.get("amenity", "unknown"),
                        "name": tags.get("name", "Unknown"),
                        "latitude": element.get("lat"),
                        "longitude": element.get("lon"),
                        "phone": tags.get("phone", tags.get("contact:phone", ""))
                    })
    except Exception as e:
        print(f"Overpass API error: {e}")
    
    return facilities


def calculate_progress(status: IncidentStatus) -> dict:
    """Calculate tracking progress based on status"""
    stages = [
        {"name": "Reported", "status": "completed", "icon": "AlertTriangle"},
        {"name": "Emergency Services Notified", "status": "pending", "icon": "Phone"},
        {"name": "NGO Responding", "status": "pending", "icon": "Heart"},
        {"name": "Resolved", "status": "pending", "icon": "CheckCircle"}
    ]
    
    status_map = {
        IncidentStatus.REPORTED: (0, 10),
        IncidentStatus.ASSIGNED_NGO: (1, 30),
        IncidentStatus.EMERGENCY_DISPATCHED: (1, 50),
        IncidentStatus.NGO_RESPONDING: (2, 70),
        IncidentStatus.ESCALATED_GOV: (2, 80),
        IncidentStatus.RESOLVED: (3, 100)
    }
    
    current_stage, progress = status_map.get(status, (0, 10))
    
    for i in range(current_stage + 1):
        stages[i]["status"] = "completed"
    if current_stage < len(stages) - 1:
        stages[current_stage]["status"] = "current"
    
    return {
        "stages": stages,
        "current_stage": current_stage,
        "progress_percentage": progress
    }


# ==================== ENDPOINTS ====================

@router.post("/", response_model=IncidentResponse)
async def create_incident(
    incident_data: IncidentCreate,
    reporter_id: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Create a new incident report"""
    
    # Reverse geocode location
    location = await reverse_geocode(incident_data.latitude, incident_data.longitude)
    
    # Map severity
    severity_map = {
        "low": IncidentSeverity.LOW,
        "medium": IncidentSeverity.MEDIUM,
        "high": IncidentSeverity.HIGH,
        "critical": IncidentSeverity.CRITICAL
    }
    severity = severity_map.get(incident_data.severity.lower(), IncidentSeverity.MEDIUM)
    
    # Create incident
    incident = Incident(
        reporter_id=uuid.UUID(reporter_id) if reporter_id else None,
        incident_type=incident_data.incident_type,
        severity=severity,
        status=IncidentStatus.REPORTED,
        latitude=incident_data.latitude,
        longitude=incident_data.longitude,
        address=location.get("display_name", ""),
        city=location.get("city", ""),
        state=location.get("state", ""),
        description=incident_data.description,
        approx_people_affected=incident_data.approx_people_affected,
        casualties=incident_data.casualties,
        terror_related=incident_data.terror_related,
        aid_needed=incident_data.aid_needed,
        image_urls=incident_data.image_urls
    )
    
    db.add(incident)
    db.commit()
    db.refresh(incident)
    
    return IncidentResponse(
        id=str(incident.id),
        incident_type=incident.incident_type,
        severity=incident.severity.value,
        status=incident.status.value,
        address=incident.address,
        city=incident.city,
        state=incident.state,
        created_at=incident.created_at
    )


@router.get("/{incident_id}")
async def get_incident(incident_id: str, db: Session = Depends(get_db)):
    """Get incident details"""
    
    incident = db.query(Incident).filter(Incident.id == incident_id).first()
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    
    return {
        "id": str(incident.id),
        "incident_type": incident.incident_type,
        "severity": incident.severity.value,
        "status": incident.status.value,
        "location": {
            "latitude": incident.latitude,
            "longitude": incident.longitude,
            "address": incident.address,
            "city": incident.city,
            "state": incident.state
        },
        "details": {
            "description": incident.description,
            "approx_people_affected": incident.approx_people_affected,
            "casualties": incident.casualties,
            "terror_related": incident.terror_related,
            "aid_needed": incident.aid_needed
        },
        "assignment": {
            "assigned_ngo_id": str(incident.assigned_ngo_id) if incident.assigned_ngo_id else None,
            "escalated_to_gov": incident.escalated_to_gov
        },
        "created_at": incident.created_at.isoformat(),
        "updated_at": incident.updated_at.isoformat() if incident.updated_at else None
    }


@router.get("/{incident_id}/track", response_model=TrackingResponse)
async def track_incident(incident_id: str, db: Session = Depends(get_db)):
    """Get incident tracking progress with nearby facilities"""
    
    incident = db.query(Incident).filter(Incident.id == incident_id).first()
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    
    # Calculate progress
    progress_data = calculate_progress(incident.status)
    
    # Get nearby facilities
    facilities = await get_nearby_facilities(incident.latitude, incident.longitude)
    
    return TrackingResponse(
        incident_id=str(incident.id),
        status=incident.status.value,
        progress_percentage=progress_data["progress_percentage"],
        stages=progress_data["stages"],
        current_stage=progress_data["current_stage"],
        nearby_facilities=facilities
    )


@router.put("/{incident_id}/assign")
async def assign_to_ngo(
    incident_id: str,
    assignment: IncidentAssign,
    sender_id: str,  # Citizen who reported
    db: Session = Depends(get_db)
):
    """Assign incident to an NGO and send notification message"""
    
    incident = db.query(Incident).filter(Incident.id == incident_id).first()
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    
    ngo = db.query(NGO).filter(NGO.id == assignment.ngo_id).first()
    if not ngo:
        raise HTTPException(status_code=404, detail="NGO not found")
    
    # Update incident
    incident.assigned_ngo_id = uuid.UUID(assignment.ngo_id)
    incident.assigned_at = datetime.utcnow()
    incident.status = IncidentStatus.ASSIGNED_NGO
    
    # Create message to NGO (to all volunteers of the NGO)
    # Get NGO admin user (simplified - get first volunteer)
    from models.db_models import VolunteerProfile
    volunteer = db.query(VolunteerProfile).filter(
        VolunteerProfile.ngo_id == assignment.ngo_id
    ).first()
    
    if volunteer:
        message = Message(
            sender_id=uuid.UUID(sender_id) if sender_id else None,
            receiver_id=volunteer.user_id,
            incident_id=incident.id,
            message_type=MessageType.INCIDENT_REPORT,
            subject=f"New Incident: {incident.incident_type}",
            content=f"Incident reported at {incident.address}. {incident.description or 'No description provided.'}",
            extra_data={
                "incident_type": incident.incident_type,
                "severity": incident.severity.value,
                "people_affected": incident.approx_people_affected
            }
        )
        db.add(message)
    
    db.commit()
    
    return {
        "incident_id": str(incident.id),
        "assigned_ngo": ngo.name,
        "status": "assigned_ngo",
        "message": f"Incident assigned to {ngo.name}"
    }


@router.put("/{incident_id}/escalate")
async def escalate_to_gov(
    incident_id: str,
    escalation: IncidentEscalate,
    escalator_id: str,  # NGO/Volunteer who is escalating
    db: Session = Depends(get_db)
):
    """Escalate incident to government authority"""
    
    incident = db.query(Incident).filter(Incident.id == incident_id).first()
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    
    # Update incident
    incident.escalated_to_gov = True
    incident.escalated_at = datetime.utcnow()
    incident.danger_scale = escalation.danger_scale
    incident.terror_related = escalation.terror_related
    incident.financial_aid_estimate = escalation.financial_aid_estimate
    incident.escalation_reason = escalation.incident_details
    incident.status = IncidentStatus.ESCALATED_GOV
    
    # Find relevant government authority based on jurisdiction
    from models.db_models import GovAuthorityAccount
    gov_authority = db.query(GovAuthorityAccount).filter(
        GovAuthorityAccount.jurisdiction.ilike(f"%{incident.state}%"),
        GovAuthorityAccount.account_status == "approved"
    ).first()
    
    if gov_authority:
        # Send escalation message to government
        message = Message(
            sender_id=uuid.UUID(escalator_id) if escalator_id else None,
            receiver_id=gov_authority.user_id,
            incident_id=incident.id,
            message_type=MessageType.ESCALATION,
            subject=f"ESCALATION: {incident.incident_type} - Danger Level {escalation.danger_scale}",
            content=escalation.incident_details,
            extra_data={
                "danger_scale": escalation.danger_scale,
                "terror_related": escalation.terror_related,
                "financial_aid_estimate": escalation.financial_aid_estimate
            }
        )
        db.add(message)
    
    db.commit()
    
    return {
        "incident_id": str(incident.id),
        "status": "escalated_gov",
        "danger_scale": escalation.danger_scale,
        "message": "Incident escalated to government authorities"
    }


@router.put("/{incident_id}/status")
async def update_status(
    incident_id: str,
    status_update: IncidentStatusUpdate,
    db: Session = Depends(get_db)
):
    """Update incident status"""
    
    incident = db.query(Incident).filter(Incident.id == incident_id).first()
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    
    status_map = {
        "reported": IncidentStatus.REPORTED,
        "assigned_ngo": IncidentStatus.ASSIGNED_NGO,
        "emergency_dispatched": IncidentStatus.EMERGENCY_DISPATCHED,
        "ngo_responding": IncidentStatus.NGO_RESPONDING,
        "escalated_gov": IncidentStatus.ESCALATED_GOV,
        "resolved": IncidentStatus.RESOLVED
    }
    
    new_status = status_map.get(status_update.status.lower())
    if not new_status:
        raise HTTPException(status_code=400, detail="Invalid status")
    
    incident.status = new_status
    
    if new_status == IncidentStatus.EMERGENCY_DISPATCHED:
        incident.emergency_dispatched_at = datetime.utcnow()
    elif new_status == IncidentStatus.NGO_RESPONDING:
        incident.ngo_responded_at = datetime.utcnow()
    elif new_status == IncidentStatus.RESOLVED:
        incident.resolved_at = datetime.utcnow()
        incident.resolution_notes = status_update.notes
    
    db.commit()
    
    return {
        "incident_id": str(incident.id),
        "status": new_status.value,
        "message": f"Status updated to {new_status.value}"
    }


@router.get("/user/{user_id}/history")
async def get_user_incidents(
    user_id: str,
    db: Session = Depends(get_db)
):
    """Get all incidents reported by a user"""
    
    incidents = db.query(Incident).filter(
        Incident.reporter_id == user_id
    ).order_by(Incident.created_at.desc()).all()
    
    return [{
        "id": str(inc.id),
        "incident_type": inc.incident_type,
        "severity": inc.severity.value,
        "status": inc.status.value,
        "city": inc.city,
        "created_at": inc.created_at.isoformat()
    } for inc in incidents]


# ==================== LOCATION ENDPOINT ====================

@router.post("/location/reverse-geocode")
async def geocode_location(location: LocationInput):
    """Convert latitude/longitude to readable address"""
    
    result = await reverse_geocode(location.latitude, location.longitude)
    return {
        "latitude": location.latitude,
        "longitude": location.longitude,
        "address": result.get("display_name", ""),
        "city": result.get("city", ""),
        "state": result.get("state", ""),
        "district": result.get("district", ""),
        "postcode": result.get("postcode", "")
    }
