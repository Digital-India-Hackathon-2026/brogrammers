"""
Offline unit tests for the ePASS intent matcher and safety gate.
No server or model required (RAG is stubbed).
"""

import os
import sys

os.environ.setdefault("LLM_PROVIDER", "none")
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import services.rag_service as _rs
_rs.RAGService.load = lambda self: None
_rs.RAGService.retrieve_with_meta = lambda self, q, top_k=3: []

from orchestrator import Orchestrator          # noqa: E402
from agents.safety import SafetyAgent          # noqa: E402
from models.schemas import DOMElement, StepResponse  # noqa: E402

_orch = Orchestrator()


def test_all_nine_services_loaded():
    assert len(_orch.workflows) == 9
    assert "postmatric_status" in _orch.workflows
    assert "prematric_fresh" in _orch.workflows


def test_keyword_intent_matching():
    wid, _ = _orch._match_workflow("check my scholarship status")
    assert wid == "postmatric_status"
    wid, _ = _orch._match_workflow("renew my pre matric scholarship")
    assert wid == "prematric_renewal"


def test_element_matcher_prefers_specific_label():
    dom = [
        DOMElement(id="", tag="a", type="", label="Post Matric Scholarship Services",
                   placeholder="", bbox={"x": 0, "y": 0, "width": 1, "height": 1},
                   selector="a.svc", sensitive_hint=False),
        DOMElement(id="", tag="a", type="", label="Home", placeholder="",
                   bbox={"x": 0, "y": 0, "width": 1, "height": 1}, selector="#home", sensitive_hint=False),
    ]
    el = _orch._match_element(["Post Matric Scholarship Services", "Post Matric"], dom)
    assert el is not None and el.selector == "a.svc"


def test_safety_blocks_otp_field():
    dom = [DOMElement(id="otp", tag="input", type="text", label="Enter OTP", placeholder="",
                      bbox={"x": 0, "y": 0, "width": 1, "height": 1}, selector="#otp", sensitive_hint=True)]
    resp = StepResponse(action="highlight", target_selector="#otp", narration_text="x", confidence_score=0.9)
    gated = SafetyAgent().check("#otp", dom, resp)
    assert gated.action == "confirm_required"


def test_safety_allows_normal_button():
    dom = [DOMElement(id="", tag="a", type="", label="Get Details", placeholder="",
                      bbox={"x": 0, "y": 0, "width": 1, "height": 1}, selector="a.btn", sensitive_hint=False)]
    resp = StepResponse(action="highlight", target_selector="a.btn", narration_text="x", confidence_score=0.9)
    out = SafetyAgent().check("a.btn", dom, resp)
    assert out.action == "highlight"


if __name__ == "__main__":
    test_all_nine_services_loaded()
    test_keyword_intent_matching()
    test_element_matcher_prefers_specific_label()
    test_safety_blocks_otp_field()
    test_safety_allows_normal_button()
    print("ALL FALLBACK TESTS PASSED")
