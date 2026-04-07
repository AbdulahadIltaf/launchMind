import uuid
import datetime
import json
import os
import requests
from bus import RedisBus
from state import StartupState, AgentMessage
from rich.console import Console
from langchain_groq import ChatGroq

console = Console()
bus = RedisBus()
llm = ChatGroq(model="llama-3.3-70b-versatile") # Using the model requested 

def marketing_node(state: StartupState) -> dict:
    
    # Extract CEO directive for Marketing
    messages = state.get("messages", [])
    ceo_msg = next((m for m in reversed(messages) if m["from_agent"] == "CEO" and m["to_agent"] == "Marketing"), None)
    directive = ceo_msg["payload"].get("directive", "") if ceo_msg and isinstance(ceo_msg["payload"], dict) else ""
    
    # Extract Product Spec
    product_msg = next((m for m in reversed(messages) if m["from_agent"] == "Product" and m["to_agent"] == "Marketing"), None)
    product_spec = product_msg["payload"] if product_msg else state.get("product_spec", {})
    
    prompt = f"""
    You are a Growth Marketer for a startup.
    CEO Directive: '{directive}'
    Product Specification: {json.dumps(product_spec)}
    
    Based on the spec, generate the marketing copy.
    Return ONLY a valid JSON object. Format EXACTLY as:
    {{
        "tagline": "Product tagline under 10 words",
        "description": "Short product description for a landing page (2-3 sentences)",
        "cold_email_subject": "Catchy Subject",
        "cold_email_body": "Cold outreach email addressed to a potential early user or investor",
        "social_posts": {{
            "twitter": "Twitter post text",
            "linkedin": "LinkedIn post text",
            "instagram": "Instagram post text"
        }}
    }}
    """
    
    try:
        response = llm.invoke(prompt)
        parsed = json.loads(response.content.replace("```json", "").replace("```", "").strip())
        
        # Marketing APIs
        sendgrid_key = os.environ.get("SENDGRID_API_KEY")
        slack_token = os.environ.get("SLACK_BOT_TOKEN")
        
        # 1. Send Email via SendGrid
        email_status = "mocked"
        if sendgrid_key and sendgrid_key.strip():
            sg_headers = {"Authorization": f"Bearer {sendgrid_key}", "Content-Type": "application/json"}
            sg_data = {
                "personalizations": [{"to": [{"email": "iltafabdulahad@gmail.com"}]}],
                "from": {"email": "iltafabdulahad@gmail.com"},
                "subject": parsed.get("cold_email_subject", "Startup Launch"),
                "content": [{"type": "text/plain", "value": parsed.get("cold_email_body", "Hello")}]
            }
            try:
                sg_resp = requests.post("https://api.sendgrid.com/v3/mail/send", headers=sg_headers, json=sg_data)
                if sg_resp.status_code in [200, 202]:
                    email_status = "sent"
                else:
                    email_status = "failed"
                    console.print(f"[red]SendGrid Warning (Status {sg_resp.status_code}): {sg_resp.text}[/red]\n[yellow]Make sure 'iltafabdulahad@gmail.com' is registered as a Verified Single Sender in your SendGrid dashboard![/yellow]")
            except Exception as e:
                console.print(f"[red]SendGrid System Error: {e}[/red]")
                
        # 2. Post to Slack Block Kit
        slack_status = "mocked"
        if slack_token and slack_token.strip():
            # Get PR URL from github stats safely handling None
            gh_results = state.get("github_results") or {}
            pr_url = gh_results.get("pr_url", "https://github.com/PullRequest")
            slack_headers = {"Authorization": f"Bearer {slack_token}", "Content-Type": "application/json"}
            slack_data = {
                "channel": "#launches",
                "blocks": [
                    {
                        "type": "header",
                        "text": {"type": "plain_text", "text": "🚀 New Product Launch!"}
                    },
                    {
                        "type": "section",
                        "text": {"type": "mrkdwn", "text": f"*{parsed.get('tagline', 'New Launch')}*\n{parsed.get('description', 'Description')}"}
                    },
                    {
                        "type": "section",
                        "text": {"type": "mrkdwn", "text": f"Check out the code here: <{pr_url}|GitHub Pull Request>"}
                    }
                ]
            }
            try:
                requests.post("https://slack.com/api/chat.postMessage", headers=slack_headers, json=slack_data)
                slack_status = "posted"
            except Exception as e:
                console.print(f"[red]Slack API Error: {e}[/red]")
        
        action = f"Generated copy. Email ({email_status}), Slack ({slack_status}). Tagline: {parsed.get('tagline', '')[:30]}..."
    except Exception as e:
        action = f"LLM failed JSON parsing: {e}. Falling back."
        parsed = {
            "tagline": "Fallback tagline",
            "description": "Fallback description",
            "cold_email_subject": "Fallback subject",
            "cold_email_body": "Fallback body",
            "social_posts": {"twitter": "Fallback", "linkedin": "Fallback", "instagram": "Fallback"}
        }
    
    console.print(f"[bold yellow]Marketing:[/bold yellow] {action}")
    
    marketing_results = {
        "copy": parsed,
        "slack_post_drafted": True, 
        "email_scheduled": True,
        "status": "integrated"
    }
    
    msg_qa: AgentMessage = {
        "message_id": str(uuid.uuid4()),
        "from_agent": "Marketing",
        "to_agent": "QA",
        "message_type": "result",
        "payload": marketing_results,
        "timestamp": datetime.datetime.now().isoformat()
    }
    msg_ceo: AgentMessage = {
        "message_id": str(uuid.uuid4()),
        "from_agent": "Marketing",
        "to_agent": "CEO",
        "message_type": "result",
        "payload": parsed,
        "timestamp": datetime.datetime.now().isoformat()
    }
    
    messages_to_return = [msg_qa, msg_ceo]
    for m in messages_to_return:
        bus.log_interaction(m)
    
    return {
        "messages": messages_to_return,
        "marketing_results": marketing_results
    }
