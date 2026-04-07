from langgraph.graph import StateGraph, START, END
from state import StartupState
from agents.ceo import ceo_node
from agents.product import product_node
from agents.engineer import engineer_node
from agents.marketing import marketing_node
from agents.qa import qa_node

def should_end(state: StartupState) -> str:
    if state.get("review_approved"):
        return END
    return "product_node"

def build_graph():
    workflow = StateGraph(StartupState)

    # Add Nodes
    workflow.add_node("ceo_node", ceo_node)
    workflow.add_node("product_node", product_node)
    workflow.add_node("engineer_node", engineer_node)
    workflow.add_node("marketing_node", marketing_node)
    workflow.add_node("qa_node", qa_node)

    # Define Edges
    workflow.add_edge(START, "ceo_node")
    
    # Parallel Execution: Product goes to Engineer & Marketing
    workflow.add_edge("product_node", "engineer_node")
    workflow.add_edge("product_node", "marketing_node")
    
    # Fan-in to QA
    workflow.add_edge("engineer_node", "qa_node")
    workflow.add_edge("marketing_node", "qa_node")
    
    workflow.add_edge("qa_node", "ceo_node")

    # Conditional logic from CEO
    workflow.add_conditional_edges(
        "ceo_node",
        should_end,
        {
            END: END,
            "product_node": "product_node"
        }
    )

    return workflow.compile()
