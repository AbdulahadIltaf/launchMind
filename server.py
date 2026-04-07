import asyncio
import os
import sys
import json

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
from typing import List

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

app = FastAPI(title="LaunchMind UI")

# Ensure static directory exists
os.makedirs("static", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

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
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                pass

manager = ConnectionManager()

class StartRequest(BaseModel):
    idea: str = "An AI-powered startup generator that automates software engineering and marketing."

@app.get("/")
async def get_index():
    return FileResponse("static/index.html")

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # Just keep connection alive
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)

async def run_workflow(idea: str):
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

    try:
        # We can use astream to yield state updates
        async for event in workflow_app.astream(initial_state):
            # Broadcast the event step forward to UI
            await manager.broadcast({
                "type": "graph_event",
                "data": event
            })
            
        await manager.broadcast({
            "type": "graph_complete",
            "data": "Workflow Completed successfully."
        })
    except Exception as e:
        await manager.broadcast({
            "type": "graph_error",
            "data": str(e)
        })

@app.post("/start")
async def start_workflow(req: StartRequest):
    # Run the graph workflow in a background task so we don't block the HTTP response
    asyncio.create_task(run_workflow(req.idea))
    return {"status": "started", "idea": req.idea}
