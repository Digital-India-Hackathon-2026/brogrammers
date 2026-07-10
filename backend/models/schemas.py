from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional


class DOMElement(BaseModel):
    id: str
    tag: str
    type: str
    label: str
    placeholder: str
    bbox: Dict[str, int]
    selector: str
    sensitive_hint: bool
    href: str = ""       # link/onclick target — helps disambiguate identical button text
    context: str = ""    # nearby section/row text — helps pick the right section


class StepRequest(BaseModel):
    session_id: str
    dom_snapshot: List[DOMElement]
    user_utterance: str
    url: Optional[str] = None
    language: str = "en"


class StepResponse(BaseModel):
    action: str = Field(description="One of: 'highlight', 'explain', 'confirm_required', 'complete'")
    target_selector: str = Field(default="", description="CSS selector of the element to highlight")
    narration_text: str = Field(description="What to tell the user")
    confidence_score: float = Field(default=0.7, description="0.0-1.0 confidence")

    # ── Navigator context (optional; drives the step UI in the extension) ──────
    workflow_id: str = Field(default="", description="Active service workflow id, if any")
    service_title: str = Field(default="", description="Human-friendly service name")
    step_index: int = Field(default=-1, description="0-based index of the current step (-1 = n/a)")
    total_steps: int = Field(default=0, description="Total steps in the active workflow")
    is_final: bool = Field(default=False, description="True when the workflow just completed")


class ServiceInfo(BaseModel):
    workflow_id: str
    title: str
    category: str = ""
    icon: str = ""
    blurb: str = ""
    external: bool = False
