"""
Local ePASS demo portal — a deliberately busy stand-in for telanganaepass.cgg.gov.in.

Served by main.py at /demo … so you can rehearse the full step-by-step navigator
(with real full-page navigations) without depending on the live government site.
The extension's content script runs here because 127.0.0.1 is in its match list.
"""

from typing import Optional

# Extra "noise" links to mimic a confusing real government portal.
_NOISE_LINKS = [
    "Home", "About Us", "Notifications", "Downloads", "Institution Login",
    "Officer Login", "Grievance", "FAQ", "RTI", "Contact Us", "Circulars",
    "User Manual", "Help Desk", "Screen Reader Access",
]

_BASE_CSS = """
:root { --navy:#0b2e6b; --navy2:#123f8f; --gold:#f4a300; --ink:#1f2937; }
* { box-sizing:border-box; }
body { margin:0; font-family:'Segoe UI',Tahoma,Arial,sans-serif; color:var(--ink); background:#eef1f6; }
a { color:var(--navy2); }
.topbar { background:#08245a; color:#cdd8ef; font-size:12px; padding:4px 16px; display:flex; justify-content:space-between; }
.header { background:linear-gradient(180deg,var(--navy),var(--navy2)); color:#fff; padding:12px 16px; display:flex; align-items:center; gap:14px; }
.emblem { width:46px; height:46px; border-radius:50%; background:#fff; color:var(--navy); display:flex; align-items:center; justify-content:center; font-weight:800; font-size:12px; text-align:center; line-height:1.1; }
.header h1 { font-size:20px; margin:0; }
.header p { margin:2px 0 0; font-size:12px; color:#c9d6f0; }
.nav { background:var(--gold); display:flex; flex-wrap:wrap; gap:2px; padding:0 8px; }
.nav a { color:#3a2a00; text-decoration:none; font-size:13px; font-weight:600; padding:8px 10px; }
.nav a:hover { background:rgba(0,0,0,.12); }
.marquee { background:#fff3cd; color:#7a5b00; font-size:13px; padding:6px 16px; border-bottom:1px solid #f0d98a; }
.wrap { max-width:1000px; margin:18px auto; padding:0 16px; }
.crumbs { font-size:12px; color:#5b6472; margin-bottom:12px; }
.panel { background:#fff; border:1px solid #dbe1ea; border-radius:8px; padding:18px 20px; margin-bottom:18px; box-shadow:0 1px 3px rgba(0,0,0,.05); }
.panel h2 { margin:0 0 14px; font-size:17px; color:var(--navy); border-bottom:2px solid var(--gold); padding-bottom:8px; }
.svc-grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(280px,1fr)); gap:12px; }
.svc { display:block; background:#f7f9fc; border:1px solid #d8e0ec; border-radius:8px; padding:14px 16px; text-decoration:none; color:var(--ink); }
.svc:hover { border-color:var(--navy2); box-shadow:0 2px 8px rgba(18,63,143,.15); }
.svc b { color:var(--navy); }
.svc span { display:block; font-size:12px; color:#64748b; margin-top:4px; }
.btn { display:inline-block; background:var(--navy2); color:#fff !important; text-decoration:none; padding:9px 18px; border-radius:6px; font-weight:600; font-size:14px; border:none; cursor:pointer; }
.btn.gold { background:var(--gold); color:#3a2a00 !important; }
.row { display:flex; flex-wrap:wrap; gap:16px; margin-bottom:12px; }
.field { flex:1 1 240px; }
.field label { display:block; font-size:13px; font-weight:600; margin-bottom:4px; color:#334155; }
.field input, .field select { width:100%; padding:8px 10px; border:1px solid #c7cfdb; border-radius:5px; font-size:14px; }
.aside { display:grid; grid-template-columns:repeat(auto-fill,minmax(160px,1fr)); gap:8px; }
.aside a { background:#eef2f9; border:1px solid #dce3ee; border-radius:6px; padding:8px 10px; font-size:12.5px; text-decoration:none; color:#334155; }
.footer { text-align:center; font-size:12px; color:#6b7280; padding:18px; }
.ok { background:#e7f7ec; border:1px solid #a6dcb6; color:#1a7a3a; padding:12px 14px; border-radius:6px; font-weight:600; }
"""


def _page(title: str, crumbs: str, body: str) -> str:
    noise = "".join(f'<a href="/demo">{t}</a>' for t in _NOISE_LINKS)
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title} — Telangana ePASS (Demo)</title><style>{_BASE_CSS}</style></head>
<body>
  <div class="topbar"><span>Government of Telangana · Social Welfare Department</span><span>Skip to main content · A- A A+</span></div>
  <div class="header">
    <div class="emblem">ePASS</div>
    <div><h1>Telangana ePASS <span style="font-size:12px;font-weight:400;">(Local Demo)</span></h1>
    <p>Electronic Payment &amp; Application System of Scholarships</p></div>
  </div>
  <div class="nav">{noise}</div>
  <div class="marquee">📢 Applications for the academic year 2026-27 are now open · Last date for Post-Matric fresh registration: 31 Aug 2026 · Keep your Aadhaar seeded to your bank account.</div>
  <div class="wrap">
    <div class="crumbs">{crumbs}</div>
    {body}
  </div>
  <div class="footer">This is a local demo of the Telangana ePASS portal for the CivicOS AI assistant. Not an official Government website.</div>
</body></html>"""


def _svc(href: str, title: str, sub: str) -> str:
    return f'<a class="svc" href="{href}"><b>{title}</b><span>{sub}</span></a>'


def _field(label: str, kind: str = "input", options=None) -> str:
    fid = "f_" + "".join(ch for ch in label.lower() if ch.isalnum())
    if kind == "select":
        opts = "".join(f"<option>{o}</option>" for o in (options or ["-- Select --"]))
        ctrl = f'<select id="{fid}" aria-label="{label}">{opts}</select>'
    else:
        ctrl = f'<input id="{fid}" type="text" aria-label="{label}" placeholder="Enter {label}">'
    return f'<div class="field"><label for="{fid}">{label}</label>{ctrl}</div>'


def _form_page(title, crumbs, heading, fields_html, submit_label, submit_href) -> str:
    body = f"""
    <div class="panel">
      <h2>{heading}</h2>
      {fields_html}
      <div style="margin-top:10px;">
        <a class="btn" href="{submit_href}">{submit_label}</a>
        <a class="btn gold" href="/demo" style="margin-left:8px;">Reset</a>
      </div>
    </div>"""
    return _page(title, crumbs, body)


# ── page builders ─────────────────────────────────────────────────────────────
def _home() -> str:
    body = f"""
    <div class="panel">
      <h2>Scholarship Services</h2>
      <div class="svc-grid">
        {_svc("/demo/postmatric", "Post Matric Scholarship Services", "Intermediate, UG, PG — fresh, renewal, status, print")}
        {_svc("/demo/prematric", "Pre Matric Scholarship Services", "Classes IX–X for SC / ST / PwD students")}
        {_svc("/demo", "Overseas Scholarships", "For SC, ST, BC, Minority students studying abroad")}
        {_svc("/demo", "Fee Reimbursement (RTF)", "Reimbursement of Tuition Fee services")}
        {_svc("/demo", "Best Available Schools", "Admissions and services")}
        {_svc("/demo", "Health Cards / Others", "Miscellaneous welfare services")}
      </div>
    </div>
    <div class="panel">
      <h2>Quick Links</h2>
      <div class="aside">
        <a href="/demo">Know Your Application Status</a><a href="/demo">Payment Status</a>
        <a href="/demo">Verification Status</a><a href="/demo">Downloads</a>
        <a href="/demo">Circulars</a><a href="/demo">Institution Search</a>
        <a href="/demo">Grievance Redressal</a><a href="/demo">Contact Officers</a>
      </div>
    </div>"""
    return _page("Home", '<a href="/demo">Home</a>', body)


def _postmatric() -> str:
    body = f"""
    <div class="panel">
      <h2>Post Matric Scholarship Services</h2>
      <div class="svc-grid">
        {_svc("/demo/postmatric/fresh", "Fresh Pre-Registration for All Department", "3. Start a new post-matric application")}
        {_svc("/demo/postmatric/renewal", "Renewal Registration", "Postmatric Scholarships For Renewal Registration (2026-27)")}
        {_svc("/demo/postmatric/print", "Print Application/Acknowledgement", "Postmatric Print Application / Acknowledgement")}
        {_svc("/demo/postmatric/status", "Know your Application Status", "Postmatric Application Status")}
        {_svc("/demo", "Payment Details", "Check disbursement details")}
        {_svc("/demo", "Edit Options", "Modify submitted application")}
      </div>
    </div>"""
    return _page("Post Matric Services", '<a href="/demo">Home</a> › Post Matric', body)


def _prematric() -> str:
    body = f"""
    <div class="panel">
      <h2>Pre Matric Scholarship Services (SC / ST / PwD)</h2>
      <div class="svc-grid">
        {_svc("/demo/prematric/registration", "Prematric Scholarships For SC/ST/PWD Students Fresh Registration — Registration", "Start a new pre-matric application")}
        {_svc("/demo/prematric/print", "Prematric Fresh — Print Application", "Print your fresh application")}
        {_svc("/demo/prematric/renewal", "Prematric Renewal Registration — Registration", "Renew your pre-matric scholarship")}
        {_svc("/demo/prematric/renewalprint", "Prematric Renewal — Print Application", "Print your renewal application")}
      </div>
    </div>"""
    return _page("Pre Matric Services", '<a href="/demo">Home</a> › Pre Matric', body)


def _result() -> str:
    body = """
    <div class="panel">
      <h2>Application Details</h2>
      <div class="ok">✔ Application Number TS-PM-2026-0098765 — Status: SANCTIONED. Amount credited to your Aadhaar-seeded bank account.</div>
      <p style="margin-top:12px;font-size:14px;">Academic Year: 2026-27 · Scheme: Post-Matric · Sanctioned on: 12-Jun-2026.</p>
      <a class="btn" href="/demo">Back to Home</a>
    </div>"""
    return _page("Application Details", '<a href="/demo">Home</a> › Details', body)


# route key -> builder (or form spec)
def render_demo_page(page: str) -> Optional[str]:
    page = (page or "home").strip("/").lower()
    crumb_pm = '<a href="/demo">Home</a> › <a href="/demo/postmatric">Post Matric</a>'
    crumb_pr = '<a href="/demo">Home</a> › <a href="/demo/prematric">Pre Matric</a>'

    if page in ("", "home"):
        return _home()
    if page == "postmatric":
        return _postmatric()
    if page == "prematric":
        return _prematric()
    if page == "result":
        return _result()

    if page == "postmatric/fresh":
        fields = "<div class='row'>" + _field("SSC Hall Ticket No") + _field("Date of Birth") + "</div>" + \
                 "<div class='row'>" + _field("SSC Pass Year") + _field("SSC Pass Type", "select", ["-- Select --", "Regular", "Supplementary"]) + "</div>"
        return _form_page("Post Matric Fresh", crumb_pm, "Fresh Pre-Registration for All Department", fields, "Get Details", "/demo/result")

    if page == "postmatric/renewal":
        fields = "<div class='row'>" + _field("Previous year ApplicationId") + _field("SSC Pass Type", "select", ["-- Select --", "Regular", "Supplementary"]) + "</div>" + \
                 "<div class='row'>" + _field("SSC HallTicket No") + _field("SSC Pass Year") + "</div>" + \
                 "<div class='row'>" + _field("Applicant Name In Aadhaar") + "</div>"
        return _form_page("Post Matric Renewal", crumb_pm, "Renewal Registration", fields, "Get Details", "/demo/result")

    if page == "postmatric/print":
        fields = "<div class='row'>" + _field("Previous year ApplicationId") + _field("SSC Pass Type", "select", ["-- Select --", "Regular", "Supplementary"]) + "</div>" + \
                 "<div class='row'>" + _field("SSC HallTicket No") + _field("SSC Pass Year") + "</div>" + \
                 "<div class='row'>" + _field("Applicant Name In Aadhaar") + "</div>"
        return _form_page("Post Matric Print", crumb_pm, "Print Application / Acknowledgement", fields, "Get Details", "/demo/result")

    if page == "postmatric/status":
        fields = "<div class='row'>" + _field("Academic Year", "select", ["-- Select --", "2026-27", "2025-26"]) + _field("Application Number") + "</div>"
        return _form_page("Post Matric Status", crumb_pm, "Know your Application Status", fields, "Status", "/demo/result")

    if page == "prematric/registration":
        fields = "<div class='row'>" + _field("Student Name (Particulars)") + _field("School Particulars") + "</div>" + \
                 "<div class='row'>" + _field("Bank Account Details") + _field("Address") + "</div>" + \
                 "<div class='row'>" + _field("Income Certificate No") + _field("Caste Certificate No") + "</div>" + \
                 "<div class='row'>" + _field("Scanned Documents") + "</div>"
        return _form_page("Pre Matric Registration", crumb_pr, "SC/ST/PWD Students Fresh Registration", fields, "Submit", "/demo/result")

    if page == "prematric/print":
        fields = "<div class='row'>" + _field("District", "select", ["-- Select --", "Hyderabad", "Warangal"]) + _field("Mandal") + "</div>" + \
                 "<div class='row'>" + _field("School") + _field("Academic Year", "select", ["-- Select --", "2026-27", "2025-26"]) + "</div>"
        return _form_page("Pre Matric Print", crumb_pr, "Print Application", fields, "Get Application", "/demo/result")

    if page == "prematric/renewal":
        fields = "<div class='row'>" + _field("Previous Application Id") + "</div>"
        return _form_page("Pre Matric Renewal", crumb_pr, "Renewal Registration", fields, "Get Application Status", "/demo/result")

    if page == "prematric/renewalprint":
        fields = "<div class='row'>" + _field("District", "select", ["-- Select --", "Hyderabad", "Warangal"]) + _field("Mandal") + "</div>" + \
                 "<div class='row'>" + _field("School") + _field("Academic Year", "select", ["-- Select --", "2026-27", "2025-26"]) + "</div>"
        return _form_page("Pre Matric Renewal Print", crumb_pr, "Print Application", fields, "Print", "/demo/result")

    return None
