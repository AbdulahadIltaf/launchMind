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

def ceo_node(state: StartupState) -> dict:
    
    qa_report = state.get("qa_report")
    idea = state.get("idea", "")
    
    if not qa_report: # First run
        prompt = f"""
        You are the CEO of a micro-startup. Your startup idea is: "{idea}"
        Break down this idea into structured tasks for three of your agents:
        1. Product Manager: Focus on core features and personas.
        2. Engineer: Focus on tech stack and landing page components.
        3. Marketing: Focus on social media and email outreach.
        
        Return ONLY a valid JSON object. Format EXACTLY as:
        {{
            "product_task": "instructions for product",
            "engineer_task": "instructions for engineer",
            "marketing_task": "instructions for marketing"
        }}
        """
        response = llm.invoke(prompt)
        try:
            payload = json.loads(response.content.replace("```json", "").replace("```", "").strip())
        except Exception:
            payload = {"product_task": "Define spec", "engineer_task": "Build code", "marketing_task": "Write marketing copy"}
            
        action = f"Decomposed idea into 3 tasks. Product task: {payload.get('product_task', '')[:30]}..."
        review_approved = False
        
        msg_product: AgentMessage = {
            "message_id": str(uuid.uuid4()),
            "from_agent": "CEO",
            "to_agent": "Product",
            "message_type": "task",
            "payload": {"directive": payload.get("product_task", "")},
            "timestamp": datetime.datetime.now().isoformat()
        }
        msg_engineer: AgentMessage = {
            "message_id": str(uuid.uuid4()),
            "from_agent": "CEO",
            "to_agent": "Engineer",
            "message_type": "task",
            "payload": {"directive": payload.get("engineer_task", "")},
            "timestamp": datetime.datetime.now().isoformat()
        }
        msg_marketing: AgentMessage = {
            "message_id": str(uuid.uuid4()),
            "from_agent": "CEO",
            "to_agent": "Marketing",
            "message_type": "task",
            "payload": {"directive": payload.get("marketing_task", "")},
            "timestamp": datetime.datetime.now().isoformat()
        }
        
        messages_to_return = [msg_product, msg_engineer, msg_marketing]
        
    else: # Second run or QA evaluation
        status = qa_report.get("status")
        comments = qa_report.get("comments", [])
        prompt = f"""
        You are the CEO. You received a QA review for your startup idea "{idea}".
        The QA status is: {status}. The issues are: {comments}.
        If status is 'fail', write a revision directive for the Product Manager to fix the issues.
        If status is 'pass', write a final announcement summary for Slack.
        Return ONLY a valid JSON object. Format: {{"directive_or_summary": "instructions or summary", "approved": boolean}}
        """
        response = llm.invoke(prompt)
        try:
            payload = json.loads(response.content.replace("```json", "").replace("```", "").strip())
        except Exception:
            payload = {"directive_or_summary": response.content, "approved": status == "pass"}
            
        review_approved = payload.get("approved", status == "pass")
        action = f"QA was {status}. CEO says: {payload.get('directive_or_summary', '')[:50]}..."
        
        if not review_approved:
            messages_to_return = [{
                "message_id": str(uuid.uuid4()),
                "from_agent": "CEO",
                "to_agent": "Product",
                "message_type": "task",
                "payload": {"directive": payload.get("directive_or_summary", "")},
                "timestamp": datetime.datetime.now().isoformat()
            }]
        else:
            summary_text = payload.get("directive_or_summary", "Final launch approved!")
            messages_to_return = [{
                "message_id": str(uuid.uuid4()),
                "from_agent": "CEO",
                "to_agent": "Slack",
                "message_type": "confirmation",
                "payload": {"slack_summary": summary_text},
                "timestamp": datetime.datetime.now().isoformat()
            }]
            
            # Send Final CEO Summary to Slack
            import os
            slack_token = os.environ.get("SLACK_BOT_TOKEN")
            if slack_token and slack_token.strip():
                try:
                    import requests
                    slack_headers = {"Authorization": f"Bearer {slack_token}", "Content-Type": "application/json"}
                    slack_data = {
                        "channel": "#launches",
                        "text": f"👨‍💼 *CEO Final Approval Summary:*\n{summary_text}"
                    }
                    requests.post("https://slack.com/api/chat.postMessage", headers=slack_headers, json=slack_data)
                except Exception as e:
                    console.print(f"[red]CEO Slack API Error: {e}[/red]")
            
    console.print(f"[bold magenta]CEO:[/bold magenta] {action}")

    for m in messages_to_return:
        bus.log_interaction(m)
    
    return {"messages": messages_to_return, "review_approved": review_approved}
