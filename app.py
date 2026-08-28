
import streamlit as st
import pandas as pd
import requests
from io import StringIO
from datetime import datetime, timezone
from rapidfuzz import fuzz, process
import plotly.graph_objects as go

st.set_page_config(
    page_title="The Absence Signal | Counterparty Reality Intelligence",
    page_icon="◌",
    layout="wide",
    initial_sidebar_state="expanded"
)

# -------------------------
# STYLE
# -------------------------
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', sans-serif;
}
.stApp {
    background: #F4F5F7;
    color: #111827;
}
.block-container {
    padding-top: 1.4rem;
    padding-bottom: 3rem;
    max-width: 1440px;
}
section[data-testid="stSidebar"] {
    background: #FFFFFF;
    border-right: 1px solid #E5E7EB;
}
section[data-testid="stSidebar"] .block-container {
    padding-top: 1.5rem;
}
h1,h2,h3 {
    letter-spacing: -0.03em;
    color: #111827;
}
hr {
    border: none;
    border-top: 1px solid #E5E7EB;
}
.hero {
    background: #FFFFFF;
    border: 1px solid #E5E7EB;
    border-radius: 18px;
    padding: 30px 32px 26px 32px;
    margin-bottom: 18px;
}
.kicker {
    font-size: 0.72rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: .13em;
    color: #6B7280;
    margin-bottom: 8px;
}
.hero-title {
    font-size: 2.55rem;
    line-height: 1.02;
    font-weight: 700;
    color: #111827;
    margin: 0;
}
.hero-sub {
    font-size: 1rem;
    line-height: 1.65;
    color: #4B5563;
    max-width: 880px;
    margin-top: 12px;
}
.pi {
    margin-top: 18px;
    font-size: .84rem;
    color: #374151;
}
.card {
    background: #FFFFFF;
    border: 1px solid #E5E7EB;
    border-radius: 14px;
    padding: 18px 20px;
    min-height: 128px;
}
.metric-label {
    font-size: .72rem;
    text-transform: uppercase;
    letter-spacing: .1em;
    font-weight: 700;
    color: #6B7280;
}
.metric-value {
    font-size: 2rem;
    line-height: 1;
    font-weight: 700;
    color: #111827;
    margin-top: 10px;
}
.metric-note {
    margin-top: 8px;
    font-size: .82rem;
    color: #6B7280;
}
.signal {
    background: #111827;
    color: white;
    border-radius: 16px;
    padding: 24px 26px;
    margin: 14px 0 18px 0;
}
.signal h2 {
    color: white;
    margin: 0;
    font-size: 1.9rem;
}
.signal p {
    color: #D1D5DB;
    margin: 8px 0 0 0;
    line-height: 1.6;
}
.section-title {
    font-size: 1.1rem;
    font-weight: 700;
    margin-top: 6px;
    margin-bottom: 10px;
}
.insight {
    background: #FFFFFF;
    border-left: 4px solid #111827;
    border-top: 1px solid #E5E7EB;
    border-right: 1px solid #E5E7EB;
    border-bottom: 1px solid #E5E7EB;
    border-radius: 10px;
    padding: 16px 18px;
    margin: 8px 0;
}
.insight strong {
    color: #111827;
}
.disclaimer {
    font-size: .78rem;
    color: #6B7280;
    margin-top: 20px;
    line-height: 1.6;
}
div[data-testid="stDataFrame"] {
    background: white;
    border-radius: 12px;
}
.stButton>button {
    border-radius: 10px;
    font-weight: 600;
}
</style>
""", unsafe_allow_html=True)

# -------------------------
# LIVE DATA
# -------------------------
@st.cache_data(ttl=1800, show_spinner=False)
def gleif_search(name: str):
    url = "https://api.gleif.org/api/v1/lei-records"
    params = {"filter[entity.legalName]": name, "page[size]": 10}
    r = requests.get(url, params=params, timeout=20)
    r.raise_for_status()
    return r.json()

@st.cache_data(ttl=3600, show_spinner=False)
def ofac_names():
    urls = [
        "https://www.treasury.gov/ofac/downloads/sdn.csv",
        "https://sanctionslistservice.ofac.treas.gov/api/PublicationPreview/exports/SDN.CSV"
    ]
    for url in urls:
        try:
            r = requests.get(url, timeout=40, allow_redirects=True)
            if r.ok and len(r.text) > 1000:
                df = pd.read_csv(StringIO(r.text), header=None, dtype=str, on_bad_lines="skip")
                if df.shape[1] >= 2:
                    return df.iloc[:, 1].dropna().astype(str).str.strip().tolist()
        except Exception:
            pass
    return []

def screen_ofac(name):
    try:
        names = ofac_names()
        if not names:
            return "Feed unavailable", None
        m, score, _ = process.extractOne(name, names, scorer=fuzz.WRatio)
        return m, int(score)
    except Exception:
        return "Feed unavailable", None

def safe(v, default="—"):
    return v if v not in [None, "", []] else default

def score_model(d):
    weights = {
        "Legal identity": 15,
        "Entity status": 10,
        "Operating history": 15,
        "Workforce footprint": 15,
        "Physical / operational presence": 15,
        "Market / trade activity": 15,
        "Digital history": 10,
        "Sanctions-name signal": 5,
    }
    gap = {}
    gap["Legal identity"] = 0 if d["gleif_found"] else 1
    gap["Entity status"] = 0 if d["lei_active"] else (0.5 if d["gleif_found"] else 1)
    gap["Operating history"] = 0 if d["claimed_years"] == 0 else 1 - min(d["observed_years"]/max(d["claimed_years"],1),1)
    gap["Workforce footprint"] = 0 if d["claimed_employees"] == 0 else 1 - min(d["observed_employees"]/max(d["claimed_employees"],1),1)
    gap["Physical / operational presence"] = 0 if d["physical_presence"] else 1
    gap["Market / trade activity"] = 0 if d["market_activity"] else 1
    gap["Digital history"] = 0 if d["digital_history"] else 1
    s = d["ofac_score"]
    gap["Sanctions-name signal"] = 0 if s is None or s < 85 else (1 if s >= 95 else .5)
    score = round(sum(weights[k]*gap[k] for k in weights))
    return score, weights, gap

# -------------------------
# SIDEBAR
# -------------------------
with st.sidebar:
    st.markdown("### Investigation Setup")
    st.caption("Public-source triage. Not a determination of wrongdoing.")
    entity_name = st.text_input("Entity / company name", placeholder="e.g. HSBC HOLDINGS PLC")
    st.markdown("---")
    st.markdown("#### Claimed profile")
    claimed_years = st.number_input("Years operating", 0, 200, 10)
    claimed_employees = st.number_input("Employees", 0, 1000000, 100)

    st.markdown("#### Observed evidence")
    observed_years = st.number_input("Verified footprint years", 0, 200, 3)
    observed_employees = st.number_input("Identifiable employees", 0, 1000000, 20)
    physical_presence = st.checkbox("Operational presence verified")
    market_activity = st.checkbox("Market / trade activity verified")
    digital_history = st.checkbox("Digital history aligns with claim")
    run = st.button("Run assessment", type="primary", use_container_width=True)

    st.markdown("---")
    st.markdown("#### Method")
    st.caption("Expected Footprint Divergence compares claimed organisational reality against observable public-source evidence.")

# -------------------------
# HEADER
# -------------------------
st.markdown("""
<div class="hero">
    <div class="kicker">Counterparty Reality Intelligence</div>
    <div class="hero-title">The Absence Signal</div>
    <div class="hero-sub">
        A public-source investigation framework for identifying where an organisation's claimed operating profile
        diverges from the footprint that should reasonably be observable.
    </div>
    <div class="pi"><b>Principal Investigator:</b> Mohd Khairul Ridhuan bin Mohd Fadzil</div>
</div>
""", unsafe_allow_html=True)

if not run:
    a,b,c = st.columns(3)
    with a:
        st.markdown("""<div class="card"><div class="metric-label">01 · Identity</div><div class="metric-value">Who are they?</div><div class="metric-note">Validate legal identity and registration footprint.</div></div>""", unsafe_allow_html=True)
    with b:
        st.markdown("""<div class="card"><div class="metric-label">02 · Reality</div><div class="metric-value">What should exist?</div><div class="metric-note">Define the footprint implied by the organisation's claims.</div></div>""", unsafe_allow_html=True)
    with c:
        st.markdown("""<div class="card"><div class="metric-label">03 · Signal</div><div class="metric-value">What is missing?</div><div class="metric-note">Convert divergence into investigation priorities.</div></div>""", unsafe_allow_html=True)

    st.markdown("""
    <div class="signal">
        <h2>The gap is the signal.</h2>
        <p>Absence is not proof. But repeated absence across expected operating footprints can be a rational trigger for deeper verification.</p>
    </div>
    """, unsafe_allow_html=True)
    st.stop()

if not entity_name.strip():
    st.error("Enter an entity or company name.")
    st.stop()

# -------------------------
# RETRIEVAL
# -------------------------
with st.spinner("Retrieving current entity intelligence..."):
    gleif_found = False
    lei_active = False
    legal_name = entity_name.strip()
    lei = "—"
    jurisdiction = "—"
    legal_address = "—"
    registration_status = "Not located in GLEIF"

    try:
        payload = gleif_search(entity_name.strip())
        records = payload.get("data", [])
        if records:
            r = records[0]
            attrs = r.get("attributes", {})
            ent = attrs.get("entity", {})
            reg = attrs.get("registration", {})
            gleif_found = True
            legal_name = safe(ent.get("legalName", {}).get("name"), entity_name.strip())
            lei = safe(attrs.get("lei"))
            jurisdiction = safe(ent.get("jurisdiction"))
            addr = ent.get("legalAddress", {})
            addr_parts = []
            if addr.get("addressLines"):
                addr_parts += addr.get("addressLines", [])
            for k in ["city","region","country"]:
                if addr.get(k): addr_parts.append(addr[k])
            legal_address = ", ".join(addr_parts) if addr_parts else "—"
            registration_status = safe(reg.get("status"))
            lei_active = str(registration_status).upper() == "ISSUED"
    except Exception:
        pass

    ofac_match, ofac_score = screen_ofac(legal_name)

inputs = {
    "gleif_found": gleif_found,
    "lei_active": lei_active,
    "claimed_years": claimed_years,
    "observed_years": observed_years,
    "claimed_employees": claimed_employees,
    "observed_employees": observed_employees,
    "physical_presence": physical_presence,
    "market_activity": market_activity,
    "digital_history": digital_history,
    "ofac_score": ofac_score
}
score, weights, gaps = score_model(inputs)

if score >= 70:
    assessment = "HIGH DIVERGENCE"
    recommendation = "Escalate for enhanced due diligence"
elif score >= 40:
    assessment = "MODERATE DIVERGENCE"
    recommendation = "Verify priority gaps before reliance"
else:
    assessment = "LOW DIVERGENCE"
    recommendation = "No major inconsistency captured"

# -------------------------
# EXECUTIVE VIEW
# -------------------------
tab1, tab2, tab3 = st.tabs(["Executive Signal", "Evidence Gap", "Analyst Brief"])

with tab1:
    st.markdown('<div class="section-title">Executive assessment</div>', unsafe_allow_html=True)
    c1,c2,c3,c4 = st.columns(4)
    cards = [
        ("Divergence Score", f"{score}/100", "Higher = greater mismatch"),
        ("Assessment", assessment, "Triage classification"),
        ("Legal Identity", "Located" if gleif_found else "Not located", "GLEIF live entity layer"),
        ("OFAC Similarity", "N/A" if ofac_score is None else f"{ofac_score}%", "Name similarity only"),
    ]
    for col,(lab,val,note) in zip([c1,c2,c3,c4],cards):
        with col:
            st.markdown(f'<div class="card"><div class="metric-label">{lab}</div><div class="metric-value">{val}</div><div class="metric-note">{note}</div></div>', unsafe_allow_html=True)

    st.markdown(f"""
    <div class="signal">
        <div class="kicker" style="color:#9CA3AF">Analytic judgement</div>
        <h2>The gap is the signal.</h2>
        <p><b>{legal_name}</b> currently produces an Expected Footprint Divergence score of <b>{score}/100</b>.
        Recommended disposition: <b>{recommendation}</b>. This is a triage judgement, not an allegation of fraud or illegality.</p>
    </div>
    """, unsafe_allow_html=True)

    left,right = st.columns([1.15,.85])
    with left:
        st.markdown('<div class="section-title">Entity identity</div>', unsafe_allow_html=True)
        df_id = pd.DataFrame([
            ["Legal name", legal_name],
            ["LEI", lei],
            ["Jurisdiction", jurisdiction],
            ["Legal address", legal_address],
            ["LEI status", registration_status],
            ["Closest OFAC SDN name", ofac_match],
        ], columns=["Field","Observed"])
        st.dataframe(df_id, use_container_width=True, hide_index=True, height=250)

    with right:
        st.markdown('<div class="section-title">Decision signal</div>', unsafe_allow_html=True)
        fig = go.Figure(go.Indicator(
            mode="gauge+number",
            value=score,
            number={'suffix': "/100"},
            gauge={
                'axis': {'range': [0,100], 'tickwidth': 1},
                'bar': {'color': '#111827'},
                'steps': [
                    {'range':[0,40], 'color':'#ECEFF3'},
                    {'range':[40,70], 'color':'#D9DDE3'},
                    {'range':[70,100], 'color':'#C6CBD3'},
                ],
            },
            title={'text': "Expected Footprint Divergence"}
        ))
        fig.update_layout(height=250, margin=dict(l=20,r=20,t=50,b=10), paper_bgcolor='white', font={'family':'Inter'})
        st.plotly_chart(fig, use_container_width=True, config={'displayModeBar':False})

with tab2:
    st.markdown('<div class="section-title">Evidence gap decomposition</div>', unsafe_allow_html=True)
    rows=[]
    for k,w in weights.items():
        contribution = round(w*gaps[k],1)
        rows.append({
            "Dimension":k,
            "Weight":w,
            "Gap severity":round(gaps[k],2),
            "Contribution":contribution,
            "Status":"Aligned" if gaps[k]==0 else ("Partial gap" if gaps[k] < 1 else "Material gap")
        })
    df = pd.DataFrame(rows).sort_values("Contribution", ascending=False)

    fig = go.Figure(go.Bar(
        x=df["Contribution"],
        y=df["Dimension"],
        orientation="h",
        marker_color="#111827",
        text=df["Contribution"],
        textposition="outside"
    ))
    fig.update_layout(
        height=430,
        xaxis_title="Contribution to divergence score",
        yaxis_title="",
        margin=dict(l=10,r=20,t=20,b=10),
        paper_bgcolor="white",
        plot_bgcolor="white",
        font={'family':'Inter'},
        yaxis={'categoryorder':'total ascending'},
        showlegend=False
    )
    st.plotly_chart(fig, use_container_width=True, config={'displayModeBar':False})

    st.dataframe(df, use_container_width=True, hide_index=True)

    st.markdown('<div class="section-title">Priority collection questions</div>', unsafe_allow_html=True)
    top = df[df["Contribution"]>0].head(5)
    prompts = {
        "Legal identity":"Can the entity's legal existence and identifiers be independently corroborated?",
        "Entity status":"Is the entity's current legal status consistent across authoritative sources?",
        "Operating history":"Does the observable chronology support the claimed operating age?",
        "Workforce footprint":"Is the identifiable workforce plausible relative to the claimed scale?",
        "Physical / operational presence":"Can facilities, offices, plants or operational assets be independently verified?",
        "Market / trade activity":"Is there observable evidence of customers, tenders, trade, logistics or procurement activity?",
        "Digital history":"Does the digital chronology pre-date or align with the claimed operating history?",
        "Sanctions-name signal":"Does the potential name similarity survive identifier-level manual review?"
    }
    if top.empty:
        st.success("No material evidence gap captured in this assessment.")
    else:
        for _,r in top.iterrows():
            st.markdown(f'<div class="insight"><strong>{r["Dimension"]}</strong><br>{prompts[r["Dimension"]]}</div>', unsafe_allow_html=True)

with tab3:
    st.markdown('<div class="section-title">Analyst brief</div>', unsafe_allow_html=True)

    st.markdown(f"""
**Judgement**

The current public-source profile for **{legal_name}** shows **{assessment.lower()}** at **{score}/100**. The signal is driven by the degree to which the organisation's stated profile exceeds the evidence presently observable.

**What we know**

- Legal identity located in GLEIF: **{"Yes" if gleif_found else "No"}**
- LEI status: **{registration_status}**
- Claimed operating history: **{claimed_years} years**
- Observed footprint history: **{observed_years} years**
- Claimed workforce: **{claimed_employees}**
- Identifiable workforce: **{observed_employees}**
- Closest OFAC SDN name similarity: **{"N/A" if ofac_score is None else str(ofac_score)+"%"}**

**What we assess**

The current divergence should be treated as a **collection and verification signal**, not as proof of wrongdoing. Where several expected footprints are simultaneously absent, the rational response is to prioritise those gaps for deeper due diligence.

**What remains unknown**

Beneficial ownership, facility authenticity, commercial counterparties, procurement exposure, logistics footprint, historic web chronology, and identifier-level sanctions reconciliation may require additional sources.

**Recommended next action**

**{recommendation}.**
""")

    st.markdown("#### Falsification check")
    st.info("A strong investigation should actively seek evidence that could reduce the divergence score. If credible independent evidence explains the apparent gaps, the assessment should be revised downward.")

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    st.markdown(f"""
<div class="disclaimer">
Assessment generated: {now}. GLEIF is queried at runtime when available; OFAC SDN names are refreshed periodically.
Expected Footprint Divergence is an analyst-designed triage framework. Public-source absence may reflect disclosure limits, jurisdictional differences, language barriers, or incomplete coverage.
</div>
""", unsafe_allow_html=True)
