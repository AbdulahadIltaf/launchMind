from typing import TypedDict, List, Annotated, Optional
import operator

class AgentMessage(TypedDict):
    message_id: str
    from_agent: str
    to_agent: str
    message_type: str  # task, result, revision, confirmation
    payload: dict
    timestamp: str

class StartupState(TypedDict):
    idea: str
    messages: Annotated[List[AgentMessage], operator.add]
    product_spec: Optional[dict]
    github_results: Optional[dict]
    marketing_results: Optional[dict]
    qa_report: Optional[dict]
    review_approved: bool
    demo_mode: bool
