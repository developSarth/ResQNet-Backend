"""
Crisis Command Center - Messaging Routes
Internal lightweight messaging between users for incident updates
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
import uuid

from app.database import get_db
from app.models.db_models import Message, User, Incident, MessageType, UserRole

router = APIRouter(prefix="/api/messages", tags=["Messages"])


# ==================== SCHEMAS ====================

class MessageCreate(BaseModel):
    receiver_id: str
    incident_id: Optional[str] = None
    subject: Optional[str] = None
    content: str
    message_type: str = "update"  # incident_report, update, escalation, system


class MessageResponse(BaseModel):
    id: str
    sender_id: Optional[str]
    sender_name: Optional[str]
    sender_role: Optional[str]
    receiver_id: str
    incident_id: Optional[str]
    message_type: str
    subject: Optional[str]
    content: str
    is_read: bool
    created_at: datetime

    class Config:
        from_attributes = True


# ==================== DOMAIN HELPERS ====================

def get_user_domain(role: UserRole) -> str:
    """Get domain identifier based on user role"""
    domain_map = {
        UserRole.CITIZEN: "citizen",
        UserRole.VOLUNTEER: "volunteer",
        UserRole.NGO: "ngo",
        UserRole.GOV_HEAD: "gov",
        UserRole.GOV_AUTHORITY: "gov",
        UserRole.GOV_OFFICER: "gov"
    }
    return domain_map.get(role, "unknown")


def format_user_identifier(user: User) -> str:
    """Format unique user identifier with domain"""
    domain = get_user_domain(user.role)
    return f"{domain}#{user.username}"


# ==================== ENDPOINTS ====================

@router.post("/", response_model=MessageResponse)
async def send_message(
    message_data: MessageCreate,
    sender_id: str,
    db: Session = Depends(get_db)
):
    """Send a message to another user"""
    
    # Validate sender
    sender = db.query(User).filter(User.id == sender_id).first()
    if not sender:
        raise HTTPException(status_code=404, detail="Sender not found")
    
    # Validate receiver
    receiver = db.query(User).filter(User.id == message_data.receiver_id).first()
    if not receiver:
        raise HTTPException(status_code=404, detail="Receiver not found")
    
    # Validate incident if provided
    incident = None
    if message_data.incident_id:
        incident = db.query(Incident).filter(Incident.id == message_data.incident_id).first()
        if not incident:
            raise HTTPException(status_code=404, detail="Incident not found")
    
    # Map message type
    type_map = {
        "incident_report": MessageType.INCIDENT_REPORT,
        "update": MessageType.UPDATE,
        "escalation": MessageType.ESCALATION,
        "system": MessageType.SYSTEM
    }
    msg_type = type_map.get(message_data.message_type.lower(), MessageType.UPDATE)
    
    # Create message
    message = Message(
        sender_id=uuid.UUID(sender_id),
        receiver_id=uuid.UUID(message_data.receiver_id),
        incident_id=uuid.UUID(message_data.incident_id) if message_data.incident_id else None,
        message_type=msg_type,
        subject=message_data.subject,
        content=message_data.content,
        extra_data={
            "sender_domain": get_user_domain(sender.role),
            "receiver_domain": get_user_domain(receiver.role)
        }
    )
    
    db.add(message)
    db.commit()
    db.refresh(message)
    
    return MessageResponse(
        id=str(message.id),
        sender_id=str(message.sender_id),
        sender_name=sender.full_name or sender.username,
        sender_role=get_user_domain(sender.role),
        receiver_id=str(message.receiver_id),
        incident_id=str(message.incident_id) if message.incident_id else None,
        message_type=message.message_type.value,
        subject=message.subject,
        content=message.content,
        is_read=message.is_read,
        created_at=message.created_at
    )


@router.get("/inbox", response_model=List[MessageResponse])
async def get_inbox(
    user_id: str,
    unread_only: bool = False,
    limit: int = Query(50, le=100),
    db: Session = Depends(get_db)
):
    """Get messages received by user"""
    
    query = db.query(Message).filter(Message.receiver_id == user_id)
    
    if unread_only:
        query = query.filter(Message.is_read == False)
    
    messages = query.order_by(Message.created_at.desc()).limit(limit).all()
    
    # Get sender info
    result = []
    for msg in messages:
        sender = db.query(User).filter(User.id == msg.sender_id).first() if msg.sender_id else None
        result.append(MessageResponse(
            id=str(msg.id),
            sender_id=str(msg.sender_id) if msg.sender_id else None,
            sender_name=sender.full_name or sender.username if sender else "System",
            sender_role=get_user_domain(sender.role) if sender else "system",
            receiver_id=str(msg.receiver_id),
            incident_id=str(msg.incident_id) if msg.incident_id else None,
            message_type=msg.message_type.value,
            subject=msg.subject,
            content=msg.content,
            is_read=msg.is_read,
            created_at=msg.created_at
        ))
    
    return result


@router.get("/sent", response_model=List[MessageResponse])
async def get_sent_messages(
    user_id: str,
    limit: int = Query(50, le=100),
    db: Session = Depends(get_db)
):
    """Get messages sent by user"""
    
    messages = db.query(Message).filter(
        Message.sender_id == user_id
    ).order_by(Message.created_at.desc()).limit(limit).all()
    
    result = []
    for msg in messages:
        receiver = db.query(User).filter(User.id == msg.receiver_id).first() if msg.receiver_id else None
        sender = db.query(User).filter(User.id == msg.sender_id).first() if msg.sender_id else None
        result.append(MessageResponse(
            id=str(msg.id),
            sender_id=str(msg.sender_id) if msg.sender_id else None,
            sender_name=sender.full_name or sender.username if sender else None,
            sender_role=get_user_domain(sender.role) if sender else None,
            receiver_id=str(msg.receiver_id),
            incident_id=str(msg.incident_id) if msg.incident_id else None,
            message_type=msg.message_type.value,
            subject=msg.subject,
            content=msg.content,
            is_read=msg.is_read,
            created_at=msg.created_at
        ))
    
    return result


@router.get("/incident/{incident_id}", response_model=List[MessageResponse])
async def get_incident_messages(
    incident_id: str,
    user_id: str,
    db: Session = Depends(get_db)
):
    """Get all messages related to an incident"""
    
    # Check incident exists
    incident = db.query(Incident).filter(Incident.id == incident_id).first()
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    
    # Get messages where user is sender or receiver
    messages = db.query(Message).filter(
        Message.incident_id == incident_id,
        (Message.sender_id == user_id) | (Message.receiver_id == user_id)
    ).order_by(Message.created_at.asc()).all()
    
    result = []
    for msg in messages:
        sender = db.query(User).filter(User.id == msg.sender_id).first() if msg.sender_id else None
        result.append(MessageResponse(
            id=str(msg.id),
            sender_id=str(msg.sender_id) if msg.sender_id else None,
            sender_name=sender.full_name or sender.username if sender else "System",
            sender_role=get_user_domain(sender.role) if sender else "system",
            receiver_id=str(msg.receiver_id),
            incident_id=str(msg.incident_id) if msg.incident_id else None,
            message_type=msg.message_type.value,
            subject=msg.subject,
            content=msg.content,
            is_read=msg.is_read,
            created_at=msg.created_at
        ))
    
    return result


@router.put("/{message_id}/read")
async def mark_as_read(
    message_id: str,
    user_id: str,
    db: Session = Depends(get_db)
):
    """Mark a message as read"""
    
    message = db.query(Message).filter(
        Message.id == message_id,
        Message.receiver_id == user_id
    ).first()
    
    if not message:
        raise HTTPException(status_code=404, detail="Message not found")
    
    message.is_read = True
    message.read_at = datetime.utcnow()
    db.commit()
    
    return {"status": "success", "message": "Message marked as read"}


@router.get("/unread-count")
async def get_unread_count(user_id: str, db: Session = Depends(get_db)):
    """Get unread message count for user"""
    
    count = db.query(Message).filter(
        Message.receiver_id == user_id,
        Message.is_read == False
    ).count()
    
    return {"unread_count": count}
