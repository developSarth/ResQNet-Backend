"""
Crisis Command Center - WebSocket Routes
WebSocket endpoints for real-time communication
"""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from app.ws_handlers.handler import manager

router = APIRouter(tags=["WebSocket"])


@router.websocket("/ws/incident/{incident_id}")
async def incident_websocket(
    websocket: WebSocket,
    incident_id: str,
    user_id: str = Query(None)
):
    """
    WebSocket for real-time incident updates.
    Citizen connects after reporting to receive status updates.
    """
    channel = f"incident:{incident_id}"
    await manager.connect(websocket, channel, user_id)
    
    try:
        # Send initial connection confirmation
        await manager.send_personal_message({
            "type": "CONNECTED",
            "channel": channel,
            "message": "Connected to incident updates"
        }, websocket)
        
        while True:
            # Keep connection alive and handle incoming messages
            data = await websocket.receive_json()
            
            # Handle client messages (e.g., citizen update, ping)
            if data.get("type") == "PING":
                await manager.send_personal_message({"type": "PONG"}, websocket)
            elif data.get("type") == "CITIZEN_UPDATE":
                # Citizen sending update about incident
                await manager.broadcast_to_channel(channel, {
                    "type": "CITIZEN_UPDATE",
                    "from_user": user_id,
                    "content": data.get("content"),
                    "willingness_to_update": data.get("willing", False)
                })
    
    except WebSocketDisconnect:
        manager.disconnect(websocket, channel, user_id)


@router.websocket("/ws/ngo/{ngo_id}")
async def ngo_websocket(
    websocket: WebSocket,
    ngo_id: str,
    user_id: str = Query(None)
):
    """
    WebSocket for NGO to receive incident reports from citizens.
    Volunteers/NGO staff connect to receive real-time reports.
    """
    channel = f"ngo:{ngo_id}"
    await manager.connect(websocket, channel, user_id)
    
    try:
        await manager.send_personal_message({
            "type": "CONNECTED",
            "channel": channel,
            "message": "Connected to NGO incident feed"
        }, websocket)
        
        while True:
            data = await websocket.receive_json()
            
            if data.get("type") == "PING":
                await manager.send_personal_message({"type": "PONG"}, websocket)
            elif data.get("type") == "ACCEPT_INCIDENT":
                # NGO accepting an incident
                await manager.broadcast_to_channel(channel, {
                    "type": "INCIDENT_ACCEPTED",
                    "incident_id": data.get("incident_id"),
                    "accepted_by": user_id
                })
            elif data.get("type") == "UPDATE_TO_CITIZEN":
                # NGO sending update to citizen
                incident_channel = f"incident:{data.get('incident_id')}"
                await manager.broadcast_to_channel(incident_channel, {
                    "type": "NGO_UPDATE",
                    "from_ngo": ngo_id,
                    "content": data.get("content")
                })
    
    except WebSocketDisconnect:
        manager.disconnect(websocket, channel, user_id)


@router.websocket("/ws/gov/{jurisdiction}")
async def gov_websocket(
    websocket: WebSocket,
    jurisdiction: str,
    user_id: str = Query(None)
):
    """
    WebSocket for government to receive escalations from NGOs.
    Government officials connect to receive critical incident alerts.
    """
    channel = f"gov:{jurisdiction}"
    await manager.connect(websocket, channel, user_id)
    
    try:
        await manager.send_personal_message({
            "type": "CONNECTED",
            "channel": channel,
            "message": f"Connected to government escalation feed for {jurisdiction}"
        }, websocket)
        
        while True:
            data = await websocket.receive_json()
            
            if data.get("type") == "PING":
                await manager.send_personal_message({"type": "PONG"}, websocket)
            elif data.get("type") == "UPDATE_TO_NGO":
                # Government sending update to NGO
                ngo_channel = f"ngo:{data.get('ngo_id')}"
                await manager.broadcast_to_channel(ngo_channel, {
                    "type": "GOV_DIRECTIVE",
                    "from_gov": user_id,
                    "content": data.get("content"),
                    "priority": data.get("priority", "normal")
                })
    
    except WebSocketDisconnect:
        manager.disconnect(websocket, channel, user_id)


@router.websocket("/ws/user/{user_id}")
async def user_websocket(
    websocket: WebSocket,
    user_id: str
):
    """
    Personal WebSocket for direct notifications to a user.
    Used for system notifications, message alerts, etc.
    """
    channel = f"user:{user_id}"
    await manager.connect(websocket, channel, user_id)
    
    try:
        await manager.send_personal_message({
            "type": "CONNECTED",
            "channel": channel,
            "message": "Connected to personal notifications"
        }, websocket)
        
        while True:
            data = await websocket.receive_json()
            
            if data.get("type") == "PING":
                await manager.send_personal_message({"type": "PONG"}, websocket)
    
    except WebSocketDisconnect:
        manager.disconnect(websocket, channel, user_id)
