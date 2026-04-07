# LaunchMind MAS

**Startup Idea:** An AI-powered startup generator that automates software engineering and marketing, enabling entrepreneurs to continuously launch and grow their software businesses rapidly with minimal overhead.

## System Architecture

LaunchMind is built natively on a **LangGraph** orchestration loop, interconnected strictly through custom structural JSON payloads routed over a dedicated **Redis Message Bus (`bus.py`)**. It utilizes dynamic recursion and error-protected tool calling natively across local and external environments.

### 🤖 The Multi-Agent Network:
1. **CEO Agent (`ceo.py`):** The orchestrator. It receives the startup idea, synthesizes three structured JSON directives (Product, Engineering, Marketing), and emits them. At the end of the loop, it intercepts QA reports. If the code failed QA, the CEO generates strict revision protocols and loops the graph backward safely. If approved, the CEO agent natively posts a final formalized launch summary block directly to **Slack**.
2. **Product Manager Agent (`product.py`):** The architect. Consumes the CEO's directive, designs the target audiences (personas), feature lists, and rigid user stories, broadcasting the final `product_spec` JSON out to the Builders.
3. **Engineer Agent (`engineer.py`):** The programmer. Dynamically drafts a beautiful modern HTML/CSS landing page satisfying the `product_spec`. It natively integrates with the **GitHub API** (generating its own branching logic from scratch, base64-encoding code into explicit commits, raising its own Issues, and formally opening a Pull Request), returning those physical URLs back into the global state.
4. **Marketing Agent (`marketing.py`):** The growth hacker. Drafts catchy subheadings, dynamic social copy, and a cold-outreach email. Automatically triggers the **Slack Block Kit API** to pitch the `#launches` channel dynamically with the PR URL, and directly bounces a live "Cold" email campaign to potential users securely via the **SendGrid API**.
5. **QA Validator Agent (`qa.py`):** The gatekeeper. Absorbs both the HTML from the Engineer and the Outbound Text from Marketing. Natively hits the **GitHub Reviews API** to drop physical "inline" Markdown comments onto the exact rewritten rows of `index.html` inside the PR if it catches failures, passing a detailed structured report explicitly to the CEO to handle recursive graph logic.

## 🛠️ Setup & Execution

### Prerequisites:
- Python 3.10+
- Docker (for the Redis Pub/Sub Message Bus)

### Instructions:
1. **Clone the repository:** 
   ```bash
   git clone https://github.com/[your-group-name]/launchmind.git
   cd launchmind
   ```
2. **Start the Message Bus:**
   Launch the decoupled Redis container:
   ```bash
   docker-compose up -d
   ```
3. **Set Up the Virtual Environment:**
   ```bash
   python -m venv venv
   source venv/Scripts/activate  # (Windows: venv\Scripts\activate)
   ```
4. **Install Dependencies:**
   ```bash
   pip install -r requirements.txt
   ```
5. **Configure Environment:**
   Copy the example file to `.env` and configure your API tokens (Never commit this file!).
   ```bash
   cp .env.example .env
   # Fill out GITHUB_TOKEN, SLACK_BOT_TOKEN, SENDGRID_API_KEY, GROQ_API_KEY
   ```
6. **Launch the MAS Node:**
   ```bash
   python main.py
   ```

## 🌍 Platform Connectivity Links

**(Note: Please manually link these out for final submission grading before recording the video!)**

- **GitHub Repository PR : https://github.com/AbdulahadIltaf/launchmind-project
- **Slack Workspace: https://launchmindgroup.slack.com/archives/C0APV56J7J9

---

*(System generated dynamically for the FAST NUCES AI MAS Course Evaluation, Spring 2026. Models implemented explicitly via `llama-3.3-70b-versatile` over ChatGroq provider routing.)*


# launchMind
