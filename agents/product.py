import uuid
import datetime
import json
from bus import RedisBus
from state import StartupState, AgentMessage
from rich.console import Console
from langchain_groq import ChatGroq
from langchain_core.prompts import PromptTemplate

console = Console()
bus = RedisBus()
llm = ChatGroq(model="llama-3.3-70b-versatile")

def product_node(state: StartupState) -> dict:
    
    idea = state.get("idea", "")
    
    # Extract CEO directive from the latest message directed to Product
    messages = state.get("messages", [])
    ceo_msg = next((m for m in reversed(messages) if m["from_agent"] == "CEO" and m["to_agent"] == "Product"), None)
    directive = ceo_msg["payload"].get("directive", "") if ceo_msg and isinstance(ceo_msg["payload"], dict) else ""
    
    prompt = f"""
    You are a Product Manager for a startup.
    Startup Idea: '{idea}'
    CEO Directive: '{directive}'
    
    Generate a highly structured JSON product spec. It MUST contain exactly these fields:
    - value_proposition: string (One sentence)
    - personas: list of dicts with keys (name, role, pain_point)
    - features: list of dicts with keys (name, description, priority) (priority 1=highest)
    - user_stories: list of strings (format: "As a [user], I want to [action] so that [benefit]")
    
    Return ONLY valid JSON.
    """
    
    try:
        response = llm.invoke(prompt)
        spec = json.loads(response.content.replace("```json", "").replace("```", "").strip())
        action = f"Generated PM Spec via LLM: {spec.get('value_proposition', 'Spec')}..."
    except Exception as e:
        action = f"LLM failed strict JSON generation: {e}. Falling back to skeleton."
        spec = {"features": [{"name": "landing_page", "description": "basic", "priority": 1}]}
        
    console.print(f"[bold blue]Product Manager:[/bold blue] {action}")
    
    msg_eng: AgentMessage = {
        "message_id": str(uuid.uuid4()),
        "from_agent": "Product",
        "to_agent": "Engineer",
        "message_type": "result",
        "payload": spec,
        "timestamp": datetime.datetime.now().isoformat()
    }
    msg_mkt: AgentMessage = {
        "message_id": str(uuid.uuid4()),
        "from_agent": "Product",
        "to_agent": "Marketing",
        "message_type": "result",
        "payload": spec,
        "timestamp": datetime.datetime.now().isoformat()
    }
    msg_ceo: AgentMessage = {
        "message_id": str(uuid.uuid4()),
        "from_agent": "Product",
        "to_agent": "CEO",
        "message_type": "confirmation",
        "payload": {"status": "Spec is ready and sent to engineering and marketing."},
        "timestamp": datetime.datetime.now().isoformat()
    }
    
    messages_to_return = [msg_eng, msg_mkt, msg_ceo]
    for m in messages_to_return:
        bus.log_interaction(m)
    
    return {
        "messages": messages_to_return,
        "product_spec": spec
    }
