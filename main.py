import os
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
from rich.console import Console
from rich.panel import Panel

console = Console()

def main():
    console.print(Panel.fit("[bold white]Starting LaunchMind MAS Demo[/bold white]", border_style="green"))
    
    app = build_graph()
    
    initial_state = {
        "idea": "An AI-powered startup generator that automates software engineering and marketing.",
        "messages": [],
        "product_spec": None,
        "github_results": None,
        "marketing_results": None,
        "qa_report": None,
        "review_approved": False
    }
    
    print("\n--- Event Stream ---\n")
    # Stream events from the graph
    for event in app.stream(initial_state):
        # Let the agent nodes do the rich printing
        pass
        
    console.print("\n[bold green]Workflow Completed![/bold green]")

if __name__ == "__main__":
    main()
