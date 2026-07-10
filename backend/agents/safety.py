"""
Safety Agent — CivicOS AI

A secondary, always-on gate. The navigator already marks OTP / final-submit steps
as sensitive (the Orchestrator turns those into 'confirm_required' directly). This
agent is the belt-and-suspenders net: if any proposed target is a credential, OTP,
or payment field, it refuses to let the agent act on it and hands control back to
the user.

Deliberately narrow: ordinary navigation controls on ePASS — "Registration",
"Get Details", "Status", "Post Matric Scholarship Services" — must stay clickable,
so generic words like "apply", "submit" and "login" are NOT auto-blocked here.
"""

import re
from typing import List
from models.schemas import DOMElement, StepResponse

# Only genuinely sensitive input surfaces.
_SENSITIVE_PATTERN = re.compile(
    r"(password|passwd|\botp\b|one[\s\-]?time[\s\-]?password|\bpin\b|\bcvv\b|captcha|"
    r"net[\s\-]?banking|netbanking|\bupi\b|credit[\s\-]?card|debit[\s\-]?card|card[\s\-]?number)",
    re.IGNORECASE,
)


class SafetyAgent:
    def __init__(self) -> None:
        pass

    def check(
        self,
        target_selector: str,
        dom_snapshot: List[DOMElement],
        current_response: StepResponse,
    ) -> StepResponse:
        # Never override an explanation or an already-gated response.
        if current_response.action in ("explain", "confirm_required", "complete"):
            return current_response

        is_sensitive = False

        # 1. Trust the client-computed sensitive_hint on the matched DOM element.
        for el in dom_snapshot:
            if el.selector == target_selector or (el.id and f"#{el.id}" == target_selector):
                if el.sensitive_hint:
                    is_sensitive = True
                break

        # 2. Fallback: inspect the selector text itself for sensitive tokens.
        if not is_sensitive and _SENSITIVE_PATTERN.search(target_selector or ""):
            is_sensitive = True

        if is_sensitive:
            return StepResponse(
                action="confirm_required",
                target_selector=target_selector,
                narration_text=(
                    "This looks like a password, OTP or payment field. For your security I won't "
                    "fill or click it — please enter it yourself."
                ),
                confidence_score=1.0,
                workflow_id=current_response.workflow_id,
                service_title=current_response.service_title,
                step_index=current_response.step_index,
                total_steps=current_response.total_steps,
            )

        return current_response
