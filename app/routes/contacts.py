"""
Crisis Command Center - Emergency Contacts API
National and state-wise emergency contact numbers
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel
from app.database import get_db

router = APIRouter(prefix="/api/contacts", tags=["Emergency Contacts"])


# ==================== STATIC CONTACT DATA ====================

# National Emergency Contacts
NATIONAL_CONTACTS = [
    {"category": "police", "name": "Police", "number": "100", "priority": 1},
    {"category": "ambulance", "name": "Ambulance", "number": "102", "priority": 2},
    {"category": "fire", "name": "Fire Brigade", "number": "101", "priority": 3},
    {"category": "emergency", "name": "National Emergency", "number": "112", "priority": 0},
    {"category": "disaster", "name": "Disaster Management (NDMA)", "number": "1070", "priority": 4},
    {"category": "women", "name": "Women Helpline", "number": "181", "priority": 5},
    {"category": "child", "name": "Child Helpline", "number": "1098", "priority": 6},
]

# Official National Security Contacts (as requested)
OFFICIAL_CONTACTS = [
    {
        "category": "national_security",
        "name": "NSG HQ Control Room",
        "number": "011-25671527",
        "email": "nsghq@nic.in",
        "alternate_email": "dutyoffr@nsg.gov.in",
        "priority": 1
    },
    {
        "category": "national_security",
        "name": "BSF Control Room",
        "number": "011-24362361",
        "alternate_number": "011-24368925/26",
        "email": "edpdte@bsf.nic.in",
        "priority": 2
    },
    {
        "category": "disaster",
        "name": "NDRF Control Room",
        "number": "011-26701700",
        "alternate_number": "1070",
        "priority": 3
    },
]

# State-wise Emergency Contacts
STATE_CONTACTS = {
    "AN": {"name": "Andaman & Nicobar", "police": "100", "ambulance": "102", "fire": "101", "cm_helpline": "1077"},
    "AP": {"name": "Andhra Pradesh", "police": "100", "ambulance": "108", "fire": "101", "cm_helpline": "1902", "disaster": "1077"},
    "AR": {"name": "Arunachal Pradesh", "police": "100", "ambulance": "102", "fire": "101"},
    "AS": {"name": "Assam", "police": "100", "ambulance": "108", "fire": "101", "cm_helpline": "1800-345-3611"},
    "BR": {"name": "Bihar", "police": "100", "ambulance": "102", "fire": "101", "cm_helpline": "1800-345-6262"},
    "CG": {"name": "Chhattisgarh", "police": "100", "ambulance": "108", "fire": "101"},
    "CH": {"name": "Chandigarh", "police": "100", "ambulance": "102", "fire": "101"},
    "DD": {"name": "Daman & Diu", "police": "100", "ambulance": "102", "fire": "101"},
    "DL": {"name": "Delhi", "police": "100", "ambulance": "102", "fire": "101", "women": "1091", "cm_helpline": "1031", "disaster": "1077"},
    "GA": {"name": "Goa", "police": "100", "ambulance": "108", "fire": "101"},
    "GJ": {"name": "Gujarat", "police": "100", "ambulance": "108", "fire": "101", "disaster": "1070"},
    "HP": {"name": "Himachal Pradesh", "police": "100", "ambulance": "102", "fire": "101"},
    "HR": {"name": "Haryana", "police": "100", "ambulance": "102", "fire": "101", "cm_helpline": "1800-180-2128"},
    "JH": {"name": "Jharkhand", "police": "100", "ambulance": "108", "fire": "101"},
    "JK": {"name": "Jammu & Kashmir", "police": "100", "ambulance": "102", "fire": "101", "cm_helpline": "1800-180-7011"},
    "KA": {"name": "Karnataka", "police": "100", "ambulance": "108", "fire": "101", "disaster": "1070"},
    "KL": {"name": "Kerala", "police": "100", "ambulance": "108", "fire": "101", "cm_helpline": "1800-425-5424", "disaster": "1077"},
    "LA": {"name": "Ladakh", "police": "100", "ambulance": "102", "fire": "101"},
    "LD": {"name": "Lakshadweep", "police": "100", "ambulance": "102", "fire": "101"},
    "MH": {"name": "Maharashtra", "police": "100", "ambulance": "108", "fire": "101", "disaster": "1077", "cm_helpline": "1800-120-8040"},
    "ML": {"name": "Meghalaya", "police": "100", "ambulance": "102", "fire": "101"},
    "MN": {"name": "Manipur", "police": "100", "ambulance": "102", "fire": "101"},
    "MP": {"name": "Madhya Pradesh", "police": "100", "ambulance": "108", "fire": "101", "cm_helpline": "181"},
    "MZ": {"name": "Mizoram", "police": "100", "ambulance": "102", "fire": "101"},
    "NL": {"name": "Nagaland", "police": "100", "ambulance": "102", "fire": "101"},
    "OD": {"name": "Odisha", "police": "100", "ambulance": "108", "fire": "101", "disaster": "1929"},
    "PB": {"name": "Punjab", "police": "100", "ambulance": "108", "fire": "101", "cm_helpline": "1100"},
    "PY": {"name": "Puducherry", "police": "100", "ambulance": "108", "fire": "101"},
    "RJ": {"name": "Rajasthan", "police": "100", "ambulance": "108", "fire": "101", "cm_helpline": "181"},
    "SK": {"name": "Sikkim", "police": "100", "ambulance": "102", "fire": "101"},
    "TN": {"name": "Tamil Nadu", "police": "100", "ambulance": "108", "fire": "101", "disaster": "1070"},
    "TS": {"name": "Telangana", "police": "100", "ambulance": "108", "fire": "101", "disaster": "1077"},
    "TR": {"name": "Tripura", "police": "100", "ambulance": "102", "fire": "101"},
    "UK": {"name": "Uttarakhand", "police": "100", "ambulance": "108", "fire": "101", "disaster": "1070"},
    "UP": {"name": "Uttar Pradesh", "police": "100", "ambulance": "108", "fire": "101", "cm_helpline": "1076", "women": "1090"},
    "WB": {"name": "West Bengal", "police": "100", "ambulance": "102", "fire": "101", "disaster": "1070"},
}


# ==================== RESPONSE SCHEMAS ====================

class EmergencyContactResponse(BaseModel):
    category: str
    name: str
    number: str
    priority: int
    alternate_number: Optional[str] = None
    email: Optional[str] = None
    alternate_email: Optional[str] = None

class StateContactResponse(BaseModel):
    state_code: str
    state_name: str
    police: str
    ambulance: str
    fire: str
    women_helpline: Optional[str] = None
    cm_helpline: Optional[str] = None
    disaster: Optional[str] = None

class AllContactsResponse(BaseModel):
    national: List[EmergencyContactResponse]
    official: List[EmergencyContactResponse]
    state: Optional[StateContactResponse] = None


# ==================== ENDPOINTS ====================

@router.get("/emergency", response_model=List[EmergencyContactResponse])
async def get_national_contacts():
    """Get national emergency contact numbers (Police, Ambulance, Fire, etc.)"""
    return sorted(NATIONAL_CONTACTS, key=lambda x: x.get("priority", 99))


@router.get("/official", response_model=List[EmergencyContactResponse])
async def get_official_contacts():
    """Get official national security contacts (NSG, BSF, NDRF)"""
    return sorted(OFFICIAL_CONTACTS, key=lambda x: x.get("priority", 99))


@router.get("/states", response_model=List[StateContactResponse])
async def get_all_state_contacts():
    """Get emergency contacts for all states"""
    result = []
    for code, data in STATE_CONTACTS.items():
        result.append(StateContactResponse(
            state_code=code,
            state_name=data["name"],
            police=data.get("police", "100"),
            ambulance=data.get("ambulance", "102"),
            fire=data.get("fire", "101"),
            women_helpline=data.get("women"),
            cm_helpline=data.get("cm_helpline"),
            disaster=data.get("disaster")
        ))
    return sorted(result, key=lambda x: x.state_name)


@router.get("/states/{state_code}", response_model=StateContactResponse)
async def get_state_contacts(state_code: str):
    """Get emergency contacts for a specific state"""
    code = state_code.upper()
    if code not in STATE_CONTACTS:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"State code '{code}' not found")
    
    data = STATE_CONTACTS[code]
    return StateContactResponse(
        state_code=code,
        state_name=data["name"],
        police=data.get("police", "100"),
        ambulance=data.get("ambulance", "102"),
        fire=data.get("fire", "101"),
        women_helpline=data.get("women"),
        cm_helpline=data.get("cm_helpline"),
        disaster=data.get("disaster")
    )


@router.get("/all", response_model=AllContactsResponse)
async def get_all_contacts(state_code: Optional[str] = None):
    """Get all emergency contacts with optional state filter"""
    state_data = None
    if state_code:
        code = state_code.upper()
        if code in STATE_CONTACTS:
            data = STATE_CONTACTS[code]
            state_data = StateContactResponse(
                state_code=code,
                state_name=data["name"],
                police=data.get("police", "100"),
                ambulance=data.get("ambulance", "102"),
                fire=data.get("fire", "101"),
                women_helpline=data.get("women"),
                cm_helpline=data.get("cm_helpline"),
                disaster=data.get("disaster")
            )
    
    return AllContactsResponse(
        national=sorted(NATIONAL_CONTACTS, key=lambda x: x.get("priority", 99)),
        official=sorted(OFFICIAL_CONTACTS, key=lambda x: x.get("priority", 99)),
        state=state_data
    )
