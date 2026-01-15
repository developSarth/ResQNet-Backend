"""
Crisis Command Center - WebSocket Handler
Real-time updates for incidents, NGO notifications, and government escalations
"""
from fastapi import WebSocket, WebSocketDisconnect
from typing import Dict, List, Set
import json
from datetime import datetime


class ConnectionManager:
    """
    Manages WebSocket connections for different channels:
    - incident:{incident_id} - Updates for a specific incident
    - ngo:{ngo_id} - Citizen reports to NGO
    - gov:{jurisdiction} - Escalations to government
    - user:{user_id} - Direct notifications to user
    """
    
    def __init__(self):
        # Active connections by channel
        self.active_connections: Dict[str, List[WebSocket]] = {}
        # User to connections mapping
        self.user_connections: Dict[str, Set[WebSocket]] = {}
    
    async def connect(self, websocket: WebSocket, channel: str, user_id: str = None):
        """Accept connection and add to channel"""
        await websocket.accept()
        
        if channel not in self.active_connections:
            self.active_connections[channel] = []
        self.active_connections[channel].append(websocket)
        
        if user_id:
            if user_id not in self.user_connections:
                self.user_connections[user_id] = set()
            self.user_connections[user_id].add(websocket)
        
        print(f"[WS] Connected to channel: {channel}")
    
    def disconnect(self, websocket: WebSocket, channel: str, user_id: str = None):
        """Remove connection from channel"""
        if channel in self.active_connections:
            if websocket in self.active_connections[channel]:
                self.active_connections[channel].remove(websocket)
            if not self.active_connections[channel]:
                del self.active_connections[channel]
        
        if user_id and user_id in self.user_connections:
            self.user_connections[user_id].discard(websocket)
            if not self.user_connections[user_id]:
                del self.user_connections[user_id]
        
        print(f"[WS] Disconnected from channel: {channel}")
    
    async def send_personal_message(self, message: dict, websocket: WebSocket):
        """Send message to specific connection"""
        try:
            await websocket.send_json(message)
        except Exception as e:
            print(f"[WS] Send error: {e}")
    
    async def broadcast_to_channel(self, channel: str, message: dict):
        """Broadcast message to all connections in a channel"""
        if channel in self.active_connections:
            disconnected = []
            for connection in self.active_connections[channel]:
                try:
                    await connection.send_json(message)
                except Exception:
                    disconnected.append(connection)
            
            # Clean up disconnected
            for conn in disconnected:
                self.active_connections[channel].remove(conn)
    
    async def send_to_user(self, user_id: str, message: dict):
        """Send message to all connections of a user"""
        if user_id in self.user_connections:
            disconnected = []
            for connection in self.user_connections[user_id]:
                try:
                    await connection.send_json(message)
                except Exception:
                    disconnected.append(connection)
            
            for conn in disconnected:
                self.user_connections[user_id].discard(conn)


# Singleton instance
manager = ConnectionManager()


# ==================== MESSAGE FORMATTERS ====================

def format_incident_update(incident_id: str, status: str, details: dict = None):
    """Format incident status update message"""
    return {
        "type": "INCIDENT_UPDATE",
        "incident_id": incident_id,
        "status": status,
        "details": details or {},
        "timestamp": datetime.utcnow().isoformat()
    }


def format_new_incident_report(incident_data: dict):
    """Format new incident report for NGO"""
    return {
        "type": "NEW_INCIDENT",
        "incident": incident_data,
        "timestamp": datetime.utcnow().isoformat()
    }


def format_escalation(incident_id: str, escalation_data: dict):
    """Format escalation message for government"""
    return {
        "type": "ESCALATION",
        "incident_id": incident_id,
        "data": escalation_data,
        "priority": "HIGH",
        "timestamp": datetime.utcnow().isoformat()
    }


def format_notification(title: str, message: str, notification_type: str = "info"):
    """Format general notification"""
    return {
        "type": "NOTIFICATION",
        "title": title,
        "message": message,
        "notification_type": notification_type,
        "timestamp": datetime.utcnow().isoformat()
    }


# ==================== BROADCAST HELPERS ====================

async def notify_incident_update(incident_id: str, status: str, details: dict = None):
    """Notify all watchers of incident update"""
    message = format_incident_update(incident_id, status, details)
    await manager.broadcast_to_channel(f"incident:{incident_id}", message)


async def notify_ngo_new_incident(ngo_id: str, incident_data: dict):
    """Notify NGO of new incident report"""
    message = format_new_incident_report(incident_data)
    await manager.broadcast_to_channel(f"ngo:{ngo_id}", message)


async def notify_gov_escalation(jurisdiction: str, incident_id: str, escalation_data: dict):
    """Notify government of escalation"""
    message = format_escalation(incident_id, escalation_data)
    await manager.broadcast_to_channel(f"gov:{jurisdiction}", message)


async def notify_user(user_id: str, title: str, message: str, notification_type: str = "info"):
    """Send notification to specific user"""
    msg = format_notification(title, message, notification_type)
    await manager.send_to_user(user_id, msg)
