import asyncio
import os
import sys
import json
import webbrowser
import time
from threading import Timer
from datetime import datetime

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List, Dict

# Load env before imports
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

from graph import build_graph

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app = FastAPI(title="LaunchMind UI")

# Ensure static directory exists
os.makedirs(os.path.join(BASE_DIR, "static"), exist_ok=True)
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")

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
        print(f"✓ Client connected. Total: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            print(f"✓ Client disconnected. Total: {len(self.active_connections)}")

    async def broadcast(self, message: dict):
        """Broadcast message to all connected clients"""
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                print(f"Error sending to client: {e}")
                disconnected.append(connection)
        
        # Clean up disconnected clients
        for conn in disconnected:
            await self.disconnect(conn)

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
    demo_mode: bool = False

@app.get("/")
async def get_index():
    """Serve the main dashboard"""
    return FileResponse(os.path.join(BASE_DIR, "static", "index.html"))

@app.get("/status")
async def get_status():
    """Get current server and workflow status"""
    return {
        "status": "running",
        "timestamp": datetime.now().isoformat(),
        "workflow": workflow_state,
        "connections": manager.get_status()
    }

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time updates"""
    await manager.connect(websocket)
    try:
        while True:
            # Keep connection alive and receive any messages
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        print(f"WebSocket error: {e}")
        try:
            manager.disconnect(websocket)
        except:
            pass

async def run_workflow(idea: str, demo_mode: bool = False):
    """Run the LLM workflow and broadcast updates"""
    workflow_state["is_running"] = True
    workflow_state["current_stage"] = "starting"
    workflow_state["start_time"] = datetime.now().isoformat()
    workflow_state["error"] = None
    
    print(f"\n{'='*60}")
    print(f"🚀 Starting workflow for idea: {idea}")
    print(f"{'='*60}\n")
    
    try:
        workflow_app = build_graph()
        
        initial_state = {
            "idea": idea,
            "messages": [],
            "product_spec": None,
            "github_results": None,
            "marketing_results": None,
            "qa_report": None,
            "review_approved": False,
            "demo_mode": demo_mode
        }
        
        # Track which agents have completed
        completed_stages = set()
        
        # Stream events from the workflow
        async for event in workflow_app.astream(initial_state):
            # Update current stage based on node names
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
            
            # Broadcast the event to all connected clients
            await manager.broadcast({
                "type": "graph_event",
                "data": event,
                "timestamp": datetime.now().isoformat()
            })
            
            # Small delay to prevent overwhelming clients
            await asyncio.sleep(0.1)
        
        # Mark workflow as complete
        workflow_state["is_running"] = False
        workflow_state["current_stage"] = "completed"
        
        await manager.broadcast({
            "type": "graph_complete",
            "data": "Workflow completed successfully",
            "timestamp": datetime.now().isoformat()
        })
        
        print("\n" + "="*60)
        print("✓ Workflow completed successfully!")
        print("="*60 + "\n")
        
    except Exception as e:
        error_msg = str(e)
        workflow_state["is_running"] = False
        workflow_state["current_stage"] = "error"
        workflow_state["error"] = error_msg
        
        print(f"\n❌ Workflow error: {error_msg}\n")
        
        await manager.broadcast({
            "type": "graph_error",
            "data": error_msg,
            "timestamp": datetime.now().isoformat()
        })

@app.post("/start")
async def start_workflow(req: StartRequest):
    """Start a new workflow"""
    idea = req.idea.strip()
    
    if not idea:
        return {"status": "error", "message": "Idea cannot be empty"}
    
    if workflow_state["is_running"]:
        return {"status": "error", "message": "Workflow already running"}
    
    demo_mode = req.demo_mode
    
    # Start workflow in background
    asyncio.create_task(run_workflow(idea, demo_mode))
    
    return {
        "status": "started",
        "idea": idea,
        "timestamp": datetime.now().isoformat()
    }

if __name__ == "__main__":
    import uvicorn
    
    # Open browser after a short delay
    def open_browser():
        time.sleep(2)
        try:
            webbrowser.open("http://localhost:8000")
        except:
            pass
    
    Timer(2, open_browser).start()
    
    print("\n" + "="*60)
    print("🚀 LaunchMind Server Starting...")
    print("📍 Frontend: http://localhost:8000")
    print("📊 Status: http://localhost:8000/status")
    print("="*60 + "\n")
    
    try:
        uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
    except KeyboardInterrupt:
        print("\n\n✓ Server stopped")
        sys.exit(0)
