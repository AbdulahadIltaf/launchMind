import asyncio
import os
import sys
import json
from datetime import datetime
from typing import List, Dict

# Set up path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load environment variables
def load_env():
    try:
        with open(".env", "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ[k] = v
    except FileNotFoundError:
        pass

load_env()

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from graph import build_graph

app = FastAPI(title="LaunchMind API")

# Add CORS middleware for Vercel deployment
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Workflow state tracking
workflow_state = {
    "is_running": False,
    "current_stage": "idle",
    "start_time": None,
    "error": None
}

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        """Broadcast message to all connected clients"""
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                disconnected.append(connection)
        
        for conn in disconnected:
            self.disconnect(conn)

    def get_status(self) -> Dict:
        """Get current connection status"""
        return {
            "connected_clients": len(self.active_connections),
            "workflow_running": workflow_state["is_running"],
            "current_stage": workflow_state["current_stage"]
        }

manager = ConnectionManager()

class StartRequest(BaseModel):
    idea: str = "An AI-powered startup generator that automates software engineering and marketing."

@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "ok", "timestamp": datetime.now().isoformat()}

@app.get("/api/status")
async def get_status():
    """Get current server and workflow status"""
    return {
        "status": "running",
        "timestamp": datetime.now().isoformat(),
        "workflow": workflow_state,
        "connections": manager.get_status()
    }

@app.websocket("/api/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time updates"""
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception:
        try:
            manager.disconnect(websocket)
        except:
            pass

async def run_workflow(idea: str):
    """Run the LLM workflow and broadcast updates"""
    workflow_state["is_running"] = True
    workflow_state["current_stage"] = "starting"
    workflow_state["start_time"] = datetime.now().isoformat()
    workflow_state["error"] = None
    
    try:
        workflow_app = build_graph()
        
        initial_state = {
            "idea": idea,
            "messages": [],
            "product_spec": None,
            "github_results": None,
            "marketing_results": None,
            "qa_report": None,
            "review_approved": False
        }
        
        completed_stages = set()
        
        async for event in workflow_app.astream(initial_state):
            for node_name in event.keys():
                if node_name in ["ceo_node", "product_node", "engineer_node", "marketing_node", "qa_node"]:
                    stage_names = {
                        "ceo_node": "CEO Planning",
                        "product_node": "Product Design", 
                        "engineer_node": "Engineering",
                        "marketing_node": "Marketing",
                        "qa_node": "QA Validation"
                    }
                    workflow_state["current_stage"] = stage_names.get(node_name, node_name)
                    completed_stages.add(workflow_state["current_stage"])
            
            await manager.broadcast({
                "type": "graph_event",
                "data": event,
                "timestamp": datetime.now().isoformat()
            })
            
            await asyncio.sleep(0.1)
        
        workflow_state["is_running"] = False
        workflow_state["current_stage"] = "completed"
        
        await manager.broadcast({
            "type": "graph_complete",
            "data": "Workflow completed successfully",
            "timestamp": datetime.now().isoformat()
        })
        
    except Exception as e:
        error_msg = str(e)
        workflow_state["is_running"] = False
        workflow_state["current_stage"] = "error"
        workflow_state["error"] = error_msg
        
        await manager.broadcast({
            "type": "graph_error",
            "data": error_msg,
            "timestamp": datetime.now().isoformat()
        })

@app.post("/api/start")
async def start_workflow(req: StartRequest):
    """Start a new workflow"""
    idea = req.idea.strip()
    
    if not idea:
        return {"status": "error", "message": "Idea cannot be empty"}
    
    if workflow_state["is_running"]:
        return {"status": "error", "message": "Workflow already running"}
    
    asyncio.create_task(run_workflow(idea))
    
    return {
        "status": "started",
        "idea": idea,
        "timestamp": datetime.now().isoformat()
    }
