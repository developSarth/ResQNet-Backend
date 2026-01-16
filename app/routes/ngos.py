"""
Crisis Command Center - NGO Routes
NGO search by location and name
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List
from math import radians, cos, sin, sqrt, atan2

from database import get_db
from models.db_models import NGO, VerificationStatus

router = APIRouter(prefix="/api/ngos", tags=["NGOs"])


# ==================== RESPONSE SCHEMAS ====================

class NGOResponse(BaseModel):
    id: str
    name: str
    city: Optional[str]
    state: Optional[str]
    distance: Optional[float] = None  # in km
    member_count: int
    verified: bool
    contact_phone: Optional[str]
    contact_email: Optional[str]

    class Config:
        from_attributes = True


# ==================== HELPER FUNCTIONS ====================

def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate distance between two points in kilometers"""
    R = 6371  # Earth's radius in km
    
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1-a))
    
    return R * c


# ==================== ENDPOINTS ====================

@router.get("/nearby", response_model=List[NGOResponse])
async def get_nearby_ngos(
    latitude: float = Query(..., description="User's latitude"),
    longitude: float = Query(..., description="User's longitude"),
    radius_km: float = Query(10.0, description="Search radius in kilometers"),
    limit: int = Query(10, description="Maximum results"),
    db: Session = Depends(get_db)
):
    """Get NGOs near a location"""
    
    # Get all active, verified NGOs with location data
    ngos = db.query(NGO).filter(
        NGO.is_active == True,
        NGO.latitude.isnot(None),
        NGO.longitude.isnot(None)
    ).all()
    
    # Calculate distances and filter
    nearby = []
    for ngo in ngos:
        distance = haversine_distance(latitude, longitude, ngo.latitude, ngo.longitude)
        if distance <= radius_km:
            nearby.append({
                "ngo": ngo,
                "distance": round(distance, 2)
            })
    
    # Sort by distance
    nearby.sort(key=lambda x: x["distance"])
    
    # Limit results
    nearby = nearby[:limit]
    
    return [
        NGOResponse(
            id=str(item["ngo"].id),
            name=item["ngo"].name,
            city=item["ngo"].city,
            state=item["ngo"].state,
            distance=item["distance"],
            member_count=item["ngo"].member_count,
            verified=item["ngo"].verification_status == VerificationStatus.APPROVED,
            contact_phone=item["ngo"].contact_phone,
            contact_email=item["ngo"].contact_email
        )
        for item in nearby
    ]


@router.get("/search", response_model=List[NGOResponse])
async def search_ngos(
    query: str = Query(..., min_length=2, description="Search query"),
    state: Optional[str] = Query(None, description="Filter by state"),
    limit: int = Query(10, description="Maximum results"),
    db: Session = Depends(get_db)
):
    """Search NGOs by name"""
    
    filters = [
        NGO.is_active == True,
        NGO.name.ilike(f"%{query}%")
    ]
    
    if state:
        filters.append(NGO.state.ilike(f"%{state}%"))
    
    ngos = db.query(NGO).filter(*filters).limit(limit).all()
    
    return [
        NGOResponse(
            id=str(ngo.id),
            name=ngo.name,
            city=ngo.city,
            state=ngo.state,
            distance=None,
            member_count=ngo.member_count,
            verified=ngo.verification_status == VerificationStatus.APPROVED,
            contact_phone=ngo.contact_phone,
            contact_email=ngo.contact_email
        )
        for ngo in ngos
    ]


@router.get("/{ngo_id}")
async def get_ngo_details(ngo_id: str, db: Session = Depends(get_db)):
    """Get NGO details"""
    
    ngo = db.query(NGO).filter(NGO.id == ngo_id).first()
    if not ngo:
        raise HTTPException(status_code=404, detail="NGO not found")
    
    return {
        "id": str(ngo.id),
        "name": ngo.name,
        "registration_number": ngo.registration_number,
        "address": ngo.address,
        "city": ngo.city,
        "state": ngo.state,
        "location": {
            "latitude": ngo.latitude,
            "longitude": ngo.longitude
        } if ngo.latitude else None,
        "contact": {
            "email": ngo.contact_email,
            "phone": ngo.contact_phone
        },
        "member_count": ngo.member_count,
        "verified": ngo.verification_status == VerificationStatus.APPROVED,
        "is_active": ngo.is_active
    }


@router.get("/{ngo_id}/incidents")
async def get_ngo_incidents(
    ngo_id: str,
    status: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Get incidents assigned to an NGO"""
    
    from models.db_models import Incident, IncidentStatus
    
    ngo = db.query(NGO).filter(NGO.id == ngo_id).first()
    if not ngo:
        raise HTTPException(status_code=404, detail="NGO not found")
    
    query = db.query(Incident).filter(Incident.assigned_ngo_id == ngo_id)
    
    if status:
        status_map = {
            "pending": [IncidentStatus.ASSIGNED_NGO],
            "active": [IncidentStatus.NGO_RESPONDING, IncidentStatus.EMERGENCY_DISPATCHED],
            "resolved": [IncidentStatus.RESOLVED],
            "escalated": [IncidentStatus.ESCALATED_GOV]
        }
        if status in status_map:
            query = query.filter(Incident.status.in_(status_map[status]))
    
    incidents = query.order_by(Incident.created_at.desc()).all()
    
    return [{
        "id": str(inc.id),
        "incident_type": inc.incident_type,
        "severity": inc.severity.value,
        "status": inc.status.value,
        "address": inc.address,
        "city": inc.city,
        "people_affected": inc.approx_people_affected,
        "assigned_at": inc.assigned_at.isoformat() if inc.assigned_at else None,
        "created_at": inc.created_at.isoformat()
    } for inc in incidents]
