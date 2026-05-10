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
    
    prompt = f"""You are a Lead Software Engineer creating a modern, professional landing page.

CEO Directive: '{directive}'
Product Specification: {json.dumps(product_spec)}

Create a BEAUTIFUL, PROFESSIONAL single-page HTML landing page that:
- Has a clean, modern design with smooth gradients and professional colors
- Includes a compelling hero section with headline and subheadline
- Features a clear value proposition with 3-4 key features
- Has a professional CTA section with a sign-up button
- Includes a footer with links
- Uses modern CSS with flexbox/grid layout
- Is fully responsive (mobile-friendly)
- Uses a professional color scheme (blues, purples, grays)
- Includes subtle animations and hover effects
- Has proper typography and spacing

Return ONLY a valid JSON object with NO markdown formatting:
{{"html_code": "FULL_HTML_HERE", "issue_title": "Landing Page", "issue_body": "Professional landing page generated", "pr_title": "Landing Page", "pr_body": "Professional landing page"}}

Make the HTML production-ready with inline CSS. No external dependencies."""
    
    try:
        response = llm.invoke(prompt)
        response_text = response.content.replace("```json", "").replace("```", "").strip()
        parsed = json.loads(response_text)
        html_code = parsed.get("html_code", "")
        
        # Ensure HTML is valid
        if not html_code or not html_code.strip().startswith("<!DOCTYPE"):
            # Fallback to a basic template
            html_code = generate_fallback_html(product_spec)
        
        gh_token = os.environ.get("GITHUB_TOKEN")
        issue_url, pr_url = "https://github.com/mock", "https://github.com/mock"
        status_msg = "Generated"
        
        if gh_token and gh_token.strip():
            headers = {
                "Authorization": f"token {gh_token}",
                "Accept": "application/vnd.github.v3+json"
            }
            repo_owner = "AbdulahadIltaf"
            repo_name = "launchmind-project"
            base_url = f"https://api.github.com/repos/{repo_owner}/{repo_name}"
            
            try:
                # 1. Create Issue
                issue_resp = requests.post(f"{base_url}/issues", headers=headers, json={
                    "title": parsed.get("issue_title", "Landing page"), 
                    "body": parsed.get("issue_body", "Generated via LaunchMind")
                }, timeout=10)
                if issue_resp.status_code == 201:
                    issue_url = issue_resp.json().get("html_url", issue_url)
                
                # 2. Get main branch SHA
                ref_resp = requests.get(f"{base_url}/git/ref/heads/main", headers=headers, timeout=10)
                base_sha = ref_resp.json().get("object", {}).get("sha", "") if ref_resp.status_code == 200 else ""
                
                if not base_sha:
                    init_data = {
                        "message": "Initialize repository",
                        "content": base64.b64encode(b"# LaunchMind Project\nInitialized by LaunchMind Agent.").decode("utf-8")
                    }
                    requests.put(f"{base_url}/contents/README.md", headers=headers, json=init_data, timeout=10)
                    ref_resp = requests.get(f"{base_url}/git/ref/heads/main", headers=headers, timeout=10)
                    base_sha = ref_resp.json().get("object", {}).get("sha", "") if ref_resp.status_code == 200 else ""
                
                if base_sha:
                    branch_name = f"landing-page-{uuid.uuid4().hex[:8]}"
                    
                    # 3. Create branch
                    requests.post(f"{base_url}/git/refs", headers=headers, json={"ref": f"refs/heads/{branch_name}", "sha": base_sha}, timeout=10)
                    
                    # 4. Commit HTML
                    b64_content = base64.b64encode(html_code.encode("utf-8")).decode("utf-8")
                    commit_data = {
                        "message": "Add professional landing page",
                        "content": b64_content,
                        "branch": branch_name,
                        "committer": {"name": "EngineerAgent", "email": "agent@launchmind.ai"}
                    }
                    
                    check_file = requests.get(f"{base_url}/contents/index.html?ref={branch_name}", headers=headers, timeout=10)
                    if check_file.status_code == 200:
                        commit_data["sha"] = check_file.json().get("sha")
                    
                    requests.put(f"{base_url}/contents/index.html", headers=headers, json=commit_data, timeout=10)
                    
                    # 5. Create Pull Request
                    pr_resp = requests.post(f"{base_url}/pulls", headers=headers, json={
                        "title": parsed.get("pr_title", "Add landing page"),
                        "body": parsed.get("pr_body", "Professional landing page for startup"),
                        "head": branch_name,
                        "base": "main"
                    }, timeout=10)
                    
                    if pr_resp.status_code == 201:
                        pr_url = pr_resp.json().get("html_url", pr_url)
                        status_msg = "✓ Deployed with PR"
                    else:
                        status_msg = "✓ Generated & Committed"
                        
            except Exception as api_err:
                status_msg = f"✓ Generated (GitHub API: {str(api_err)[:30]})"
        else:
            status_msg = "✓ Generated (GitHub not configured)"
        
        action = f"Generated professional landing page. {status_msg}"
        
    except Exception as e:
        action = f"HTML generation failed: {str(e)[:50]}. Using fallback."
        html_code = generate_fallback_html(product_spec)
        issue_url, pr_url = "https://github.com/mock", "https://github.com/mock"
        status_msg = "Fallback template"
    
    console.print(f"[bold green]Engineer:[/bold green] {action}")
    
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

def generate_fallback_html(product_spec):
    """Generate a professional fallback HTML landing page."""
    product_name = product_spec.get("name", "Our Product") if isinstance(product_spec, dict) else "Our Product"
    product_desc = product_spec.get("description", "An amazing product") if isinstance(product_spec, dict) else "An amazing product"
    
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{product_name} - Next Generation Product</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: #333;
            line-height: 1.6;
        }}
        
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            padding: 0 20px;
        }}
        
        header {{
            background: rgba(255, 255, 255, 0.95);
            padding: 20px 0;
            box-shadow: 0 2px 10px rgba(0, 0, 0, 0.1);
            position: sticky;
            top: 0;
            z-index: 100;
        }}
        
        nav {{
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        
        .logo {{
            font-size: 24px;
            font-weight: 800;
            background: linear-gradient(135deg, #667eea, #764ba2);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }}
        
        .nav-links {{
            display: flex;
            gap: 30px;
            list-style: none;
        }}
        
        .nav-links a {{
            text-decoration: none;
            color: #333;
            font-weight: 500;
            transition: color 0.3s;
        }}
        
        .nav-links a:hover {{
            color: #667eea;
        }}
        
        .hero {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 120px 0;
            text-align: center;
            margin-top: -40px;
            padding-top: 160px;
        }}
        
        .hero h1 {{
            font-size: 56px;
            margin-bottom: 20px;
            font-weight: 800;
            letter-spacing: -1px;
        }}
        
        .hero .subtitle {{
            font-size: 22px;
            margin-bottom: 40px;
            opacity: 0.95;
            font-weight: 300;
        }}
        
        .cta-button {{
            display: inline-block;
            background: white;
            color: #667eea;
            padding: 16px 40px;
            border-radius: 8px;
            text-decoration: none;
            font-weight: 700;
            font-size: 16px;
            transition: all 0.3s;
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.2);
        }}
        
        .cta-button:hover {{
            transform: translateY(-3px);
            box-shadow: 0 15px 40px rgba(0, 0, 0, 0.3);
        }}
        
        .features {{
            padding: 80px 0;
            background: white;
        }}
        
        .features-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 40px;
            margin-top: 50px;
        }}
        
        .feature-card {{
            padding: 30px;
            background: #f8f9fa;
            border-radius: 10px;
            text-align: center;
            transition: all 0.3s;
            border: 1px solid #e9ecef;
        }}
        
        .feature-card:hover {{
            background: white;
            box-shadow: 0 10px 30px rgba(102, 126, 234, 0.1);
            transform: translateY(-5px);
        }}
        
        .feature-icon {{
            font-size: 48px;
            margin-bottom: 20px;
        }}
        
        .feature-card h3 {{
            font-size: 20px;
            margin-bottom: 15px;
            color: #333;
        }}
        
        .feature-card p {{
            color: #666;
            font-size: 15px;
        }}
        
        .cta-section {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 80px 0;
            text-align: center;
        }}
        
        .cta-section h2 {{
            font-size: 40px;
            margin-bottom: 30px;
        }}
        
        footer {{
            background: #1a1a1a;
            color: white;
            padding: 40px 0;
            text-align: center;
        }}
        
        footer p {{
            margin-bottom: 10px;
        }}
    </style>
</head>
<body>
    <header>
        <nav class="container">
            <div class="logo">🚀 {product_name}</div>
            <ul class="nav-links">
                <li><a href="#features">Features</a></li>
                <li><a href="#cta">Get Started</a></li>
                <li><a href="#contact">Contact</a></li>
            </ul>
        </nav>
    </header>
    
    <section class="hero">
        <div class="container">
            <h1>{product_name}</h1>
            <p class="subtitle">{product_desc}</p>
            <a href="#cta" class="cta-button">Get Started Now</a>
        </div>
    </section>
    
    <section id="features" class="features">
        <div class="container">
            <h2 style="text-align: center; font-size: 36px; margin-bottom: 10px;">Why Choose {product_name}?</h2>
            <p style="text-align: center; color: #666; margin-bottom: 30px;">Explore our powerful features designed for success</p>
            
            <div class="features-grid">
                <div class="feature-card">
                    <div class="feature-icon">⚡</div>
                    <h3>Lightning Fast</h3>
                    <p>Experience blazing fast performance with our optimized infrastructure</p>
                </div>
                <div class="feature-card">
                    <div class="feature-icon">🔒</div>
                    <h3>Secure & Reliable</h3>
                    <p>Enterprise-grade security with 99.9% uptime guarantee</p>
                </div>
                <div class="feature-card">
                    <div class="feature-icon">🎨</div>
                    <h3>Beautiful Design</h3>
                    <p>Intuitive interface crafted for the best user experience</p>
                </div>
                <div class="feature-card">
                    <div class="feature-icon">🚀</div>
                    <h3>Easy to Use</h3>
                    <p>Get started in minutes with our simple onboarding process</p>
                </div>
            </div>
        </div>
    </section>
    
    <section id="cta" class="cta-section">
        <div class="container">
            <h2>Ready to Transform Your Business?</h2>
            <p style="font-size: 18px; margin-bottom: 30px;">Join thousands of satisfied users</p>
            <button class="cta-button" style="background: white; color: #667eea; cursor: pointer; border: none;">
                Start Your Free Trial
            </button>
        </div>
    </section>
    
    <footer>
        <div class="container">
            <p>&copy; 2025 {product_name}. All rights reserved.</p>
            <p>Built with ❤️ by the LaunchMind Team</p>
        </div>
    </footer>
</body>
</html>"""
    
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
