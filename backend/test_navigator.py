"""
CivicOS AI — ePASS Navigator test (self-contained, no server, no model).

Covers the 3-step workflow model: deterministic chip start (__start__), section-context
disambiguation (two identical "Registration" buttons), the 'form' step, the login-gate
hold across routes, and completion. Run:
    ..\.venv\Scripts\python.exe test_navigator.py    (or: pytest test_navigator.py)
"""

import os
import sys

os.environ.setdefault("LLM_PROVIDER", "none")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import services.rag_service as _rs
_rs.RAGService.load = lambda self: None
_rs.RAGService.retrieve_with_meta = lambda self, q, top_k=3: []

from orchestrator import Orchestrator            # noqa: E402
from models.schemas import StepRequest           # noqa: E402

_orch = Orchestrator()


def _el(label, selector, sid="", tag="a", typ="", sens=False, ph="", href="", ctx=""):
    return {"id": sid, "tag": tag, "type": typ, "label": label, "placeholder": ph,
            "bbox": {"x": 0, "y": 0, "width": 90, "height": 24}, "selector": selector,
            "sensitive_hint": sens, "href": href, "context": ctx}


_NOISE = [_el(t, f"#n{i}") for i, t in enumerate(["Home", "About Us", "Login", "FAQ"])]
HOME = _NOISE + [_el("Post Matric Scholarship Services", "a.svc1"),
                 _el("Pre Matric Scholarship Services", "a.svc2")]
POSTM = _NOISE + [
    _el("Fresh Pre-Registrations for All Department", "a.f", ctx="Postmatric Scholarships For Fresh Registration 2026-27"),
    _el("Know your Application Status", "a.s", ctx="Postmatric Application Status"),
]
STATUS = _NOISE + [_el("Academic Year", "#ay", tag="select", ph="Academic Year"),
                   _el("Application Number", "#an", tag="input", ph="Application Number"),
                   _el("Status", "a.btn")]
RESULT = _NOISE + [_el("Back to Home", "a.b")]
# Two identical "Registration" buttons — only the section context differs.
PREM = _NOISE + [
    _el("Registration", "a.r1", href="prematricFreshRegistration",
        ctx="1.Prematric Scholarships For SC/ST/PWD Students Fresh Registration 2026-27 Registration"),
    _el("Registration", "a.r2", href="prematricRenewal",
        ctx="2.Prematric Scholarships For SC/ST/BC Renewal Registration 2026-27 Registration Print application"),
]
LOGIN = _NOISE + [_el("password", "#p", tag="input", typ="password", sens=True, ph="password"),
                  _el("captcha", "#c", tag="input", ph="captcha"), _el("Login", "a.login")]
REGFORM = _NOISE + [_el("Student Name", "#sn", tag="input", ph="Student Name"), _el("Submit", "a.sub")]


def _step(sid, utt, dom, url="http://127.0.0.1:8000/demo"):
    return _orch.handle_step(StepRequest(session_id=sid, user_utterance=utt, dom_snapshot=dom, url=url))


def test_status_flow_three_steps_with_form():
    sid = "t-status"
    r0 = _step(sid, "__start__:postmatric_status", HOME)
    assert r0.action == "highlight" and r0.workflow_id == "postmatric_status" and r0.step_index == 0
    r1 = _step(sid, "", POSTM)
    assert r1.action == "highlight" and r1.step_index == 1 and r1.target_selector == "a.s"
    r2 = _step(sid, "", STATUS)
    assert r2.action == "form" and r2.step_index == 2 and r2.target_selector == "a.btn"
    r3 = _step(sid, "", RESULT)
    assert r3.action == "complete"


def test_deterministic_chip_start():
    assert _step("t-c1", "__start__:postmatric_fresh", HOME).workflow_id == "postmatric_fresh"
    assert _step("t-c2", "__start__:prematric_renewal", HOME).workflow_id == "prematric_renewal"


def test_section_context_disambiguation():
    _step("t-f", "__start__:prematric_fresh", HOME)
    assert _step("t-f", "", PREM).target_selector == "a.r1"      # fresh section
    _step("t-r", "__start__:prematric_renewal", HOME)
    assert _step("t-r", "", PREM).target_selector == "a.r2"      # renewal section


def test_login_gate_holds_then_advances():
    sid = "t-gate"
    _step(sid, "__start__:prematric_fresh", HOME)
    _step(sid, "", PREM)
    at_login = _step(sid, "", LOGIN, url="https://tgepass.cgg.gov.in/Logout")
    assert at_login.action == "confirm_required" and at_login.step_index == 1
    at_form = _step(sid, "", REGFORM, url="https://tgepass.cgg.gov.in/homeService")
    assert at_form.action == "confirm_required" and at_form.step_index == 2 and at_form.target_selector == "a.sub"


if __name__ == "__main__":
    test_status_flow_three_steps_with_form()
    test_deterministic_chip_start()
    test_section_context_disambiguation()
    test_login_gate_holds_then_advances()
    print("ALL NAVIGATOR TESTS PASSED")
