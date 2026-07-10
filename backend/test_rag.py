"""
Live smoke test against a running backend (uvicorn on 127.0.0.1:8000).
Exercises the /step navigator over the local demo DOM and the /services catalog.

Start the backend first, then:  ..\.venv\Scripts\python.exe test_rag.py
"""

import httpx

BASE = "http://127.0.0.1:8000"
SID = "smoke-001"


def _el(label, selector, tag="a", sens=False):
    return {"id": "", "tag": tag, "type": "", "label": label, "placeholder": "",
            "bbox": {"x": 0, "y": 0, "width": 100, "height": 30},
            "selector": selector, "sensitive_hint": sens}


HOME = [_el("Post Matric Scholarship Services", "a.svc:nth-of-type(1)"),
        _el("Pre Matric Scholarship Services", "a.svc:nth-of-type(2)"),
        _el("Login", "#login")]


def step(client, utt, dom, url=f"{BASE}/demo"):
    r = client.post(f"{BASE}/api/v1/step", json={
        "session_id": SID, "user_utterance": utt, "dom_snapshot": dom, "url": url}, timeout=30)
    r.raise_for_status()
    return r.json()


def main():
    with httpx.Client() as c:
        health = c.get(f"{BASE}/api/v1/health").json()
        print("[OK] health:", health)

        services = c.get(f"{BASE}/api/v1/services").json()["services"]
        print(f"[OK] {len(services)} services in catalog")
        assert len(services) >= 8

        d = step(c, "help me check my scholarship status", HOME)
        print(f"[OK] status intent -> action={d['action']} wf={d['workflow_id']} step={d['step_index']}/{d['total_steps']}")
        assert d["workflow_id"] == "postmatric_status"
        assert d["action"] == "highlight"

        # demo page should render
        home = c.get(f"{BASE}/demo").text
        assert "Post Matric Scholarship Services" in home
        print("[OK] demo home page renders")

        print("\nSMOKE TEST PASSED")


if __name__ == "__main__":
    main()
