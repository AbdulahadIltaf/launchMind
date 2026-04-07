import uuid
import datetime
import json
import base64
import os
import requests
from bus import RedisBus
from state import StartupState, AgentMessage
from rich.console import Console
from langchain_groq import ChatGroq

console = Console()
bus = RedisBus()
llm = ChatGroq(model="llama-3.3-70b-versatile")

def engineer_node(state: StartupState) -> dict:
    
    # Extract CEO directive for Engineer
    messages = state.get("messages", [])
    ceo_msg = next((m for m in reversed(messages) if m["from_agent"] == "CEO" and m["to_agent"] == "Engineer"), None)
    directive = ceo_msg["payload"].get("directive", "") if ceo_msg and isinstance(ceo_msg["payload"], dict) else ""
    
    # Extract Product Spec
    product_msg = next((m for m in reversed(messages) if m["from_agent"] == "Product" and m["to_agent"] == "Engineer"), None)
    product_spec = product_msg["payload"] if product_msg else state.get("product_spec", {})
    
    prompt = f"""
    You are a Lead Software Engineer for a startup.
    CEO Directive: '{directive}'
    Product Specification: {json.dumps(product_spec)}
    
    Generate a complete, working single-page HTML landing page based on this spec.
    Include a headline, subheadline, features section, CTA button, and basic modern CSS styling within <style>.
    
    Return ONLY a valid JSON object. Escape your HTML properly for a JSON string.
    Format EXACTLY as:
    {{
        "html_code": "<!DOCTYPE html><html>...</html>",
        "issue_title": "Initial landing page",
        "issue_body": "Description of the landing page features",
        "pr_title": "Initial landing page",
        "pr_body": "Description of the PR"
    }}
    """
    
    try:
        response = llm.invoke(prompt)
        parsed = json.loads(response.content.replace("```json", "").replace("```", "").strip())
        html_code = parsed.get("html_code", "<html><body>Failed to generate HTML</body></html>")
        
        gh_token = os.environ.get("GITHUB_TOKEN")
        issue_url, pr_url = "https://github.com/mock", "https://github.com/mock"
        status_msg = "mocked"
        
        if gh_token and gh_token.strip():
            headers = {
                "Authorization": f"token {gh_token}",
                "Accept": "application/vnd.github.v3+json"
            }
            # Directly target the project repo
            repo_owner = "AbdulahadIltaf"
            repo_name = "launchmind-project"
            base_url = f"https://api.github.com/repos/{repo_owner}/{repo_name}"
            
            try:
                # 1. Create Issue
                issue_resp = requests.post(f"{base_url}/issues", headers=headers, json={
                    "title": parsed.get("issue_title", "Initial landing page"), 
                    "body": parsed.get("issue_body", "Generated via LaunchMind")
                })
                if issue_resp.status_code == 201:
                    issue_url = issue_resp.json().get("html_url", issue_url)
                
                # 2. Get main branch SHA for branching
                ref_resp = requests.get(f"{base_url}/git/ref/heads/main", headers=headers)
                base_sha = ref_resp.json().get("object", {}).get("sha", "") if ref_resp.status_code == 200 else ""
                
                # If repository is completely empty, GitHub API cannot branch. We must initialize it first.
                if not base_sha:
                    init_data = {
                        "message": "Initialize repository",
                        "content": base64.b64encode(b"# LaunchMind Project\nInitialized by LaunchMind Agent.").decode("utf-8")
                    }
                    requests.put(f"{base_url}/contents/README.md", headers=headers, json=init_data)
                    
                    # Fetch the SHA again now that 'main' exists
                    ref_resp = requests.get(f"{base_url}/git/ref/heads/main", headers=headers)
                    base_sha = ref_resp.json().get("object", {}).get("sha", "") if ref_resp.status_code == 200 else ""
                
                if base_sha:
                    branch_name = f"landing-page-{uuid.uuid4().hex[:8]}"
                    
                    # 3. Create new branch
                    requests.post(f"{base_url}/git/refs", headers=headers, json={"ref": f"refs/heads/{branch_name}", "sha": base_sha})
                    
                    # 4. Commit HTTP
                    b64_content = base64.b64encode(html_code.encode("utf-8")).decode("utf-8")
                    commit_data = {
                        "message": "Add generated landing page",
                        "content": b64_content,
                        "branch": branch_name,
                        "committer": {"name": "EngineerAgent", "email": "agent@launchmind.ai"}
                    }
                    # Optional protection: check if we are overwriting an existing index.html
                    check_file = requests.get(f"{base_url}/contents/index.html?ref={branch_name}", headers=headers)
                    if check_file.status_code == 200:
                        commit_data["sha"] = check_file.json().get("sha")
                        
                    requests.put(f"{base_url}/contents/index.html", headers=headers, json=commit_data)
                    
                    # 5. Open Pull Request
                    pr_resp = requests.post(f"{base_url}/pulls", headers=headers, json={
                        "title": parsed.get("pr_title", "Landing Page PR"),
                        "body": parsed.get("pr_body", "Please review the generated landing page HTML code."),
                        "head": branch_name,
                        "base": "main"
                    })
                    if pr_resp.status_code == 201:
                        pr_url = pr_resp.json().get("html_url", pr_url)
                        
                status_msg = "success"
                action = f"Generated & Deployed! Issue & PR opened on {repo_name}."
            except Exception as api_err:
                action = f"Generated HTML, but GitHub API failed ({api_err}). Mocking returns."
        else:
            action = f"Generated HTML landing page ({len(html_code)} chars). Missing GITHUB_TOKEN, skipping APIs."

    except Exception as e:
        action = f"LLM failed JSON parsing: {e}. Falling back."
        html_code = "<html><body><h1>Fallback Landing Page</h1></body></html>"
        issue_url, pr_url, status_msg = "https://github.com/mock", "https://github.com/mock", "fallback"
    
    console.print(f"[bold green]Engineer:[/bold green] {action}")
    
    # Pack up the results
    github_results = {
        "html_code": html_code,
        "pr_url": pr_url, 
        "issue_url": issue_url,
        "status": status_msg
    }
    
    msg_qa: AgentMessage = {
        "message_id": str(uuid.uuid4()),
        "from_agent": "Engineer",
        "to_agent": "QA",
        "message_type": "result",
        "payload": github_results,
        "timestamp": datetime.datetime.now().isoformat()
    }
    
    msg_ceo: AgentMessage = {
        "message_id": str(uuid.uuid4()),
        "from_agent": "Engineer",
        "to_agent": "CEO",
        "message_type": "result",
        "payload": {
            "pr_url": pr_url,
            "issue_url": issue_url
        },
        "timestamp": datetime.datetime.now().isoformat()
    }
    
    messages_to_return = [msg_qa, msg_ceo]
    for m in messages_to_return:
        bus.log_interaction(m)
    
    return {
        "messages": messages_to_return,
        "github_results": github_results
    }
