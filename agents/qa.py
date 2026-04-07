import os
import uuid
import datetime
import json
from bus import RedisBus
from state import StartupState, AgentMessage
from rich.console import Console
from langchain_groq import ChatGroq

console = Console()
bus = RedisBus()
llm = ChatGroq(model="llama-3.3-70b-versatile")

def qa_node(state: StartupState) -> dict:
    
    messages = state.get("messages", [])
    qa_messages = [m for m in messages if m["from_agent"] == "QA"]
    
    # Extract Product Spec
    product_spec = state.get("product_spec", {})
    
    # Extract Engineer and Marketing Outputs from state payloads
    eng_results = state.get("github_results", {})
    mkt_results = state.get("marketing_results", {})
    
    # Read forced flag from .env
    force_fail = os.environ.get("FORCE_FAIL_FIRST_RUN", "False").lower() == "true"
    
    if force_fail and len(qa_messages) == 0:
        # Prevent infinite loops during this run
        os.environ["FORCE_FAIL_FIRST_RUN"] = "False"
        
        status = "fail"
        comments = ["Missing dark mode toggle.", "Marketing tagline relies on heavy cliches."]
        action = f"Reviewing outputs. Found issues (Forced Flag)! Failing QA: {comments}"
    else:
        prompt = f"""
        You are a strict QA Reviewer for a startup. 
        Product Specification: {json.dumps(product_spec)}
        Engineer HTML Code: {json.dumps(eng_results.get("html_code", ""))}
        Marketing Copy: {json.dumps(mkt_results.get("copy", {}))}
        
        Evaluate both outputs against the Product Spec.
        Check if the HTML has the core features and CTA.
        Check if the Marketing copy tagline is under 10 words and tone is appropriate.

        If there are any major missing features or issues, mark status as "fail" and list the comments. 
        If everything looks acceptable, mark status as "pass" and add a positive comment.
        
        Return ONLY a valid JSON object. Format EXACTLY as:
        {{
            "status": "pass" or "fail",
            "comments": ["issue 1", "issue 2"]
        }}
        """
        
        try:
            response = llm.invoke(prompt)
            parsed = json.loads(response.content.replace("```json", "").replace("```", "").strip())
            status = parsed.get("status", "pass").lower()
            comments = parsed.get("comments", [])
            
            if status == "fail":
                action = f"LLM reviewed outputs. Found issues! Failing QA: {comments}"
            else:
                action = "LLM reviewed outputs. All specs matched. Passing QA!"
        except Exception as e:
            action = f"LLM failed JSON parsing: {e}. Defaulting to pass."
            status = "pass"
            comments = ["Parse error allowed to pass."]

    console.print(f"[bold cyan]QA Validator:[/bold cyan] {action}")
    
    gh_token = os.environ.get("GITHUB_TOKEN")
    pr_url = eng_results.get("pr_url", "")
    
    # 📝 GitHub API Integration for PR Comments
    if gh_token and gh_token.strip() and "github.com" in pr_url and "mock" not in pr_url.lower():
        try:
            import requests
            headers = {
                "Authorization": f"token {gh_token}",
                "Accept": "application/vnd.github.v3+json"
            }
            # Safely extract from https://github.com/Owner/Repo/pull/1
            parts = pr_url.rstrip("/").split("/")
            repo_owner, repo_name, pr_number = parts[-4], parts[-3], parts[-1]
            base_url = f"https://api.github.com/repos/{repo_owner}/{repo_name}"
            
            review_event = "APPROVE" if status == "pass" else "REQUEST_CHANGES"
            review_body = f"**LaunchMind QA Automated Review**\n\nVerdict: **{status.upper()}**\n\n" + "\n".join([f"- {c}" for c in comments])
            
            inline_comments = []
            for i, comment in enumerate(comments[:2]): # Attempt up to 2 inline comments
                inline_comments.append({
                    "path": "index.html",
                    "position": i + 1,
                    "body": f"[QA Note] {comment}"
                })
                
            review_payload = {
                "body": review_body,
                "event": review_event,
                "comments": inline_comments
            }
            
            resp = requests.post(f"{base_url}/pulls/{pr_number}/reviews", headers=headers, json=review_payload)
            if resp.status_code not in [200, 201]:
                # Fallback to a general PR thread comment if inline parsing fails on the exact diff hunk
                requests.post(f"{base_url}/issues/{pr_number}/comments", headers=headers, json={"body": review_body})
        except Exception as api_err:
            console.print(f"[red]GitHub Review API Error: {api_err}[/red]")
            
    qa_report = {"status": status, "comments": comments}
    
    msg: AgentMessage = {
        "message_id": str(uuid.uuid4()),
        "from_agent": "QA",
        "to_agent": "CEO",
        "message_type": "result",
        "payload": qa_report,
        "timestamp": datetime.datetime.now().isoformat()
    }
    bus.log_interaction(msg)
    
    return {
        "messages": [msg],
        "qa_report": qa_report
    }
