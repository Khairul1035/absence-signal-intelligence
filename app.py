
import os
import streamlit as st
import pandas as pd
import requests
from io import StringIO
from datetime import datetime, timezone
from rapidfuzz import fuzz, process
import plotly.graph_objects as go
import plotly.express as px

st.set_page_config(
    page_title="The Absence Signal | Intelligence Workbench",
    page_icon="◌",
    layout="wide",
    initial_sidebar_state="expanded"
)

# =========================
# CONSTANTS
# =========================
PI_NAME = "Mohd Khairul Ridhuan bin Mohd Fadzil"
FRAMEWORK = "Expected Footprint Divergence (EFD)"
VERSION = "V2.0"

# =========================
# DESIGN
# =========================
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
html, body, [class*="css"] {font-family:'Inter',sans-serif;}
.stApp {background:#F5F6F8;color:#111827;}
.block-container {padding-top:1.2rem;padding-bottom:3rem;max-width:1500px;}
section[data-testid="stSidebar"] {background:#FFFFFF;border-right:1px solid #E5E7EB;}
h1,h2,h3 {letter-spacing:-.03em;color:#111827;}
.hero {background:#FFFFFF;border:1px solid #E5E7EB;border-radius:18px;padding:28px 30px;margin-bottom:16px;}
.kicker {font-size:.7rem;font-weight:700;text-transform:uppercase;letter-spacing:.14em;color:#6B7280;}
.hero-title {font-size:2.55rem;line-height:1.02;font-weight:700;margin:5px 0 0 0;}
.hero-sub {max-width:930px;color:#4B5563;font-size:1rem;line-height:1.65;margin-top:12px;}
.pi {margin-top:17px;font-size:.82rem;color:#374151;}
.card {background:#FFFFFF;border:1px solid #E5E7EB;border-radius:14px;padding:17px 19px;min-height:118px;}
.mlabel {font-size:.69rem;text-transform:uppercase;letter-spacing:.1em;font-weight:700;color:#6B7280;}
.mvalue {font-size:1.8rem;font-weight:700;color:#111827;margin-top:8px;line-height:1.1;}
.mnote {font-size:.79rem;color:#6B7280;margin-top:7px;}
.dark {background:#111827;color:#FFFFFF;border-radius:16px;padding:23px 25px;margin:14px 0;}
.dark h2 {color:#FFFFFF;font-size:1.75rem;margin:0;}
.dark p {color:#D1D5DB;margin:7px 0 0 0;line-height:1.6;}
.section {font-size:1.05rem;font-weight:700;margin:8px 0 10px 0;}
.callout {background:#FFFFFF;border-left:4px solid #111827;border-top:1px solid #E5E7EB;border-right:1px solid #E5E7EB;border-bottom:1px solid #E5E7EB;border-radius:10px;padding:14px 16px;margin:7px 0;}
.micro {font-size:.76rem;color:#6B7280;line-height:1.55;}
.footer {font-size:.72rem;color:#6B7280;margin-top:24px;line-height:1.6;}
.badge {display:inline-block;border:1px solid #D1D5DB;border-radius:999px;padding:4px 9px;font-size:.72rem;margin-right:6px;color:#374151;background:white;}
.stButton>button {border-radius:10px;font-weight:600;}
</style>
""", unsafe_allow_html=True)

# =========================
# HELPERS
# =========================
def get_secret(name, default=""):
    try:
        return st.secrets.get(name, os.getenv(name, default))
    except Exception:
        return os.getenv(name, default)

@st.cache_data(ttl=1800, show_spinner=False)
def gleif_search(name):
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
                    return df.iloc[:,1].dropna().astype(str).str.strip().tolist()
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

@st.cache_data(ttl=900, show_spinner=False)
def companies_house_search(name, api_key):
    if not api_key:
        return None
    r = requests.get(
        "https://api.company-information.service.gov.uk/search/companies",
        params={"q": name, "items_per_page": 5},
        auth=(api_key, ""),
        timeout=20
    )
    if r.status_code != 200:
        return None
    return r.json()

@st.cache_data(ttl=1800, show_spinner=False)
def opencorporates_search(name, api_token):
    if not api_token:
        return None
    url = "https://api.opencorporates.com/v0.4/companies/search"
    r = requests.get(url, params={"q": name, "api_token": api_token, "per_page": 5}, timeout=20)
    if r.status_code != 200:
        return None
    return r.json()

def safe(v, default="—"):
    return v if v not in [None,"",[]] else default

def efd_score(d):
    weights = {
        "Legal identity": 12,
        "Cross-source identity consistency": 10,
        "Entity status": 8,
        "Operating history": 13,
        "Workforce footprint": 13,
        "Physical / operational presence": 12,
        "Market / trade activity": 12,
        "Digital history": 8,
        "Ownership / network transparency": 7,
        "Sanctions-name signal": 5,
    }
    g = {}
    g["Legal identity"] = 0 if d["identity_hits"] >= 1 else 1
    g["Cross-source identity consistency"] = 0 if d["identity_hits"] >= 2 else (0.5 if d["identity_hits"] == 1 else 1)
    g["Entity status"] = 0 if d["lei_active"] else (0.5 if d["gleif_found"] else 1)
    g["Operating history"] = 0 if d["claimed_years"] == 0 else 1-min(d["observed_years"]/max(d["claimed_years"],1),1)
    g["Workforce footprint"] = 0 if d["claimed_employees"] == 0 else 1-min(d["observed_employees"]/max(d["claimed_employees"],1),1)
    g["Physical / operational presence"] = 0 if d["physical_presence"] else 1
    g["Market / trade activity"] = 0 if d["market_activity"] else 1
    g["Digital history"] = 0 if d["digital_history"] else 1
    g["Ownership / network transparency"] = 0 if d["ownership_visibility"] else 1
    s = d["ofac_score"]
    g["Sanctions-name signal"] = 0 if s is None or s < 85 else (1 if s >= 95 else .5)
    score = round(sum(weights[k]*g[k] for k in weights))
    return score, weights, g

def confidence_score(source_count, verified_checks, total_checks=4):
    base = min(source_count/3,1)*55
    evidence = min(verified_checks/total_checks,1)*45
    return round(base+evidence)

# =========================
# SIDEBAR
# =========================
with st.sidebar:
    st.markdown("### Investigation Setup")
    st.caption("Public-source triage and collection prioritisation.")
    entity_name = st.text_input("Entity / company name", placeholder="e.g. HSBC HOLDINGS PLC")

    st.markdown("---")
    st.markdown("#### Claimed operating profile")
    claimed_years = st.number_input("Claimed years operating", 0, 200, 10)
    claimed_employees = st.number_input("Claimed employees", 0, 1_000_000, 100)

    st.markdown("#### Observed footprint")
    observed_years = st.number_input("Verified footprint years", 0, 200, 3)
    observed_employees = st.number_input("Identifiable employees", 0, 1_000_000, 20)
    physical_presence = st.checkbox("Operational presence verified")
    market_activity = st.checkbox("Market / trade activity verified")
    digital_history = st.checkbox("Digital history aligns with claim")
    ownership_visibility = st.checkbox("Ownership / network visibility adequate")

    st.markdown("---")
    st.markdown("#### Optional live connectors")
    ch_key = get_secret("COMPANIES_HOUSE_API_KEY")
    oc_key = get_secret("OPENCORPORATES_API_TOKEN")
    st.caption("Companies House: " + ("connected" if ch_key else "not configured"))
    st.caption("OpenCorporates: " + ("connected" if oc_key else "not configured"))

    run = st.button("Run intelligence assessment", type="primary", use_container_width=True)

# =========================
# HEADER
# =========================
st.markdown(f"""
<div class="hero">
  <div class="kicker">Counterparty Reality Intelligence · {VERSION}</div>
  <div class="hero-title">The Absence Signal</div>
  <div class="hero-sub">
    An investigation workbench for testing whether an organisation's claimed operating reality
    is consistent with the footprint that should reasonably be observable across authoritative and public sources.
  </div>
  <div class="pi"><b>Principal Investigator:</b> {PI_NAME}</div>
</div>
""", unsafe_allow_html=True)

if not run:
    c1,c2,c3,c4 = st.columns(4)
    intro = [
        ("01 · Resolve","Identity","Who is the entity, exactly?"),
        ("02 · Compare","Reality","What should exist if the claims are true?"),
        ("03 · Test","Evidence","What can be independently corroborated?"),
        ("04 · Judge","Signal","What gap deserves collection next?")
    ]
    for col,(k,v,n) in zip([c1,c2,c3,c4],intro):
        with col:
            st.markdown(f'<div class="card"><div class="mlabel">{k}</div><div class="mvalue">{v}</div><div class="mnote">{n}</div></div>', unsafe_allow_html=True)
    st.markdown('<div class="dark"><h2>The gap is the signal.</h2><p>Absence is never treated as proof. Repeated, unexplained absence across expected footprints is treated as a rational trigger for deeper verification.</p></div>', unsafe_allow_html=True)
    st.stop()

if not entity_name.strip():
    st.error("Enter an entity or company name first.")
    st.stop()

# =========================
# LIVE COLLECTION
# =========================
with st.spinner("Resolving entity across live sources..."):
    # GLEIF
    gleif_found=False; lei_active=False; legal_name=entity_name.strip()
    lei="—"; jurisdiction="—"; legal_address="—"; registration_status="Not located"
    gleif_raw=None
    try:
        gleif_raw=gleif_search(entity_name.strip())
        recs=gleif_raw.get("data",[])
        if recs:
            rec=recs[0]
            attrs=rec.get("attributes",{})
            ent=attrs.get("entity",{})
            reg=attrs.get("registration",{})
            gleif_found=True
            legal_name=safe(ent.get("legalName",{}).get("name"),entity_name.strip())
            lei=safe(attrs.get("lei"))
            jurisdiction=safe(ent.get("jurisdiction"))
            addr=ent.get("legalAddress",{})
            parts=[]
            if addr.get("addressLines"): parts += addr["addressLines"]
            for k in ["city","region","country"]:
                if addr.get(k): parts.append(addr[k])
            legal_address=", ".join(parts) if parts else "—"
            registration_status=safe(reg.get("status"))
            lei_active=str(registration_status).upper()=="ISSUED"
    except Exception:
        pass

    # Companies House
    ch = companies_house_search(entity_name.strip(), ch_key)
    ch_item = None
    if ch and ch.get("items"):
        ch_item = ch["items"][0]

    # OpenCorporates
    oc = opencorporates_search(entity_name.strip(), oc_key)
    oc_company = None
    try:
        companies = oc["results"]["companies"] if oc else []
        if companies:
            oc_company = companies[0]["company"]
    except Exception:
        pass

    ofac_match, ofac_score = screen_ofac(legal_name)

# =========================
# ENTITY RESOLUTION
# =========================
source_hits = []
if gleif_found:
    source_hits.append(("GLEIF", legal_name, jurisdiction, lei, "Authoritative LEI reference data"))
if ch_item:
    source_hits.append(("Companies House", safe(ch_item.get("title")), "United Kingdom", safe(ch_item.get("company_number")), "Official UK corporate register"))
if oc_company:
    source_hits.append(("OpenCorporates", safe(oc_company.get("name")), safe(oc_company.get("jurisdiction_code")), safe(oc_company.get("company_number")), "Aggregated primary-source corporate data"))

identity_hits=len(source_hits)
inputs={
    "identity_hits":identity_hits,
    "gleif_found":gleif_found,
    "lei_active":lei_active,
    "claimed_years":claimed_years,
    "observed_years":observed_years,
    "claimed_employees":claimed_employees,
    "observed_employees":observed_employees,
    "physical_presence":physical_presence,
    "market_activity":market_activity,
    "digital_history":digital_history,
    "ownership_visibility":ownership_visibility,
    "ofac_score":ofac_score,
}
score, weights, gaps = efd_score(inputs)
verified_checks=sum([physical_presence,market_activity,digital_history,ownership_visibility])
conf=confidence_score(identity_hits,verified_checks)

if score>=70:
    assessment="HIGH DIVERGENCE"; recommendation="Escalate for enhanced due diligence"
elif score>=40:
    assessment="MODERATE DIVERGENCE"; recommendation="Verify priority gaps before reliance"
else:
    assessment="LOW DIVERGENCE"; recommendation="No major inconsistency captured"

if conf>=75:
    confidence="HIGH"
elif conf>=45:
    confidence="MODERATE"
else:
    confidence="LOW"

# =========================
# TABS
# =========================
tabs=st.tabs(["Executive Signal","Entity Resolution","Evidence Ledger","Chronology & Network","Analyst Brief"])

with tabs[0]:
    st.markdown('<div class="section">Executive assessment</div>', unsafe_allow_html=True)
    cols=st.columns(5)
    metrics=[
        ("EFD Score",f"{score}/100","Higher = greater mismatch"),
        ("Assessment",assessment,"Triage class"),
        ("Confidence",confidence,f"{conf}/100 evidence confidence"),
        ("Source Hits",str(identity_hits),"Independent entity sources"),
        ("OFAC Similarity","N/A" if ofac_score is None else f"{ofac_score}%","Name similarity only")
    ]
    for c,(a,b,n) in zip(cols,metrics):
        with c:
            st.markdown(f'<div class="card"><div class="mlabel">{a}</div><div class="mvalue">{b}</div><div class="mnote">{n}</div></div>', unsafe_allow_html=True)

    st.markdown(f"""
    <div class="dark">
      <div class="kicker" style="color:#9CA3AF">Analytic judgement</div>
      <h2>The gap is the signal.</h2>
      <p><b>{legal_name}</b> produces an Expected Footprint Divergence score of <b>{score}/100</b>
      with <b>{confidence.lower()} confidence</b>. Recommended disposition: <b>{recommendation}</b>.
      This is an investigative triage judgement—not an allegation of wrongdoing.</p>
    </div>
    """, unsafe_allow_html=True)

    left,right=st.columns([1.2,.8])
    with left:
        st.markdown('<div class="section">Top drivers</div>', unsafe_allow_html=True)
        rows=[]
        for k,w in weights.items():
            rows.append({"Dimension":k,"Contribution":round(w*gaps[k],1)})
        ddf=pd.DataFrame(rows).sort_values("Contribution",ascending=False)
        top=ddf[ddf["Contribution"]>0].head(5)
        if top.empty:
            st.success("No material gap captured.")
        else:
            for _,r in top.iterrows():
                st.markdown(f'<div class="callout"><b>{r["Dimension"]}</b><br><span class="micro">Contribution to EFD: {r["Contribution"]} points</span></div>',unsafe_allow_html=True)

    with right:
        fig=go.Figure(go.Indicator(
            mode="gauge+number",value=score,number={'suffix':'/100'},
            gauge={'axis':{'range':[0,100]},
                   'bar':{'color':'#111827'},
                   'steps':[{'range':[0,40],'color':'#ECEFF3'},{'range':[40,70],'color':'#D9DDE3'},{'range':[70,100],'color':'#C7CCD4'}]},
            title={'text':'Expected Footprint Divergence'}
        ))
        fig.update_layout(height=300,margin=dict(l=20,r=20,t=55,b=5),paper_bgcolor='white',font={'family':'Inter'})
        st.plotly_chart(fig,use_container_width=True,config={'displayModeBar':False})

with tabs[1]:
    st.markdown('<div class="section">Cross-source entity resolution</div>', unsafe_allow_html=True)
    if source_hits:
        rdf=pd.DataFrame(source_hits,columns=["Source","Resolved name","Jurisdiction","Identifier","Source role"])
        st.dataframe(rdf,use_container_width=True,hide_index=True)
    else:
        st.warning("No independent entity source returned a match. This is a collection gap, not proof that the entity does not exist.")

    st.markdown("#### GLEIF reference")
    st.dataframe(pd.DataFrame([
        ["Legal name",legal_name],
        ["LEI",lei],
        ["Jurisdiction",jurisdiction],
        ["Legal address",legal_address],
        ["LEI status",registration_status],
        ["Closest OFAC SDN name",ofac_match],
    ],columns=["Field","Observed"]),use_container_width=True,hide_index=True)

    st.markdown("#### Analyst interpretation")
    if identity_hits>=2:
        st.success("Identity is corroborated across multiple independent sources. Entity-resolution confidence is materially stronger.")
    elif identity_hits==1:
        st.info("Identity is currently supported by one live source. Additional independent corroboration would improve confidence.")
    else:
        st.warning("Identity is unresolved across the configured live sources. Escalate collection before drawing substantive conclusions.")

with tabs[2]:
    st.markdown('<div class="section">Evidence ledger</div>', unsafe_allow_html=True)
    st.caption("Separate observed facts from analyst judgement. Provenance and confidence matter as much as the finding itself.")
    ledger=pd.DataFrame([
        ["Legal identity","GLEIF / configured registries","Verified" if identity_hits else "Unresolved","High" if identity_hits>=2 else "Moderate" if identity_hits==1 else "Low","Entity resolution"],
        ["Operating history","Analyst-observed chronology",f"{observed_years} of {claimed_years} claimed years","Moderate","Chronology gap"],
        ["Workforce footprint","Analyst-observed public footprint",f"{observed_employees} of {claimed_employees} claimed employees","Moderate","Scale plausibility"],
        ["Operational presence","Public-source verification","Verified" if physical_presence else "Not verified","Moderate","Capability"],
        ["Market / trade activity","Public-source verification","Verified" if market_activity else "Not verified","Moderate","Commercial reality"],
        ["Digital history","Public-source verification","Aligned" if digital_history else "Not aligned / unresolved","Moderate","Temporal consistency"],
        ["Ownership transparency","Corporate / network sources","Adequate" if ownership_visibility else "Incomplete","Moderate","Network transparency"],
        ["Sanctions-name similarity","OFAC SDN list","N/A" if ofac_score is None else f"{ofac_score}%","Low until identifiers checked","Screening cue"],
    ],columns=["Evidence question","Source / method","Current finding","Confidence","Intelligence role"])
    st.dataframe(ledger,use_container_width=True,hide_index=True)

    st.markdown("#### Evidence discipline")
    st.markdown("""
- **Fact:** directly observed or sourced.
- **Assessment:** analyst interpretation of the facts.
- **Gap:** information required before reliance.
- **Falsifier:** evidence that would materially weaken the current hypothesis.
""")

with tabs[3]:
    st.markdown('<div class="section">Chronology & network cues</div>', unsafe_allow_html=True)
    st.caption("V2 treats time and relationships as analytic dimensions, even where data still requires manual collection.")

    chrono=pd.DataFrame([
        ["Claimed operating start", max(datetime.now().year-claimed_years,1900), "Claim"],
        ["Observed footprint start", max(datetime.now().year-observed_years,1900), "Observed"],
        ["Current assessment", datetime.now().year, "Assessment"]
    ],columns=["Event","Year","Type"])
    fig=px.scatter(chrono,x="Year",y="Type",text="Event",size=[18,18,18])
    fig.update_traces(textposition="top center")
    fig.update_layout(height=320,showlegend=False,paper_bgcolor="white",plot_bgcolor="white",font={'family':'Inter'})
    st.plotly_chart(fig,use_container_width=True,config={'displayModeBar':False})

    st.markdown("#### Network questions to collect next")
    network_q=[
        "Do directors, addresses, agents or parent entities recur across other companies?",
        "Are ownership links consistent across registries and corporate disclosures?",
        "Does the entity share infrastructure, contact details, or counterparties with higher-risk nodes?",
        "Do relationship dates precede, coincide with, or follow key corporate or procurement events?",
        "Can any proximity signal be explained by ordinary commercial structure?"
    ]
    for q in network_q:
        st.markdown(f'<div class="callout">{q}</div>',unsafe_allow_html=True)

with tabs[4]:
    st.markdown('<div class="section">Analyst brief</div>', unsafe_allow_html=True)
    st.markdown(f"""
**Principal Investigator:** {PI_NAME}

**Question**

Does the observable public-source footprint of **{legal_name}** reasonably support its stated operating profile?

**What we know**

- Independent entity sources returning a usable match: **{identity_hits}**
- GLEIF identity located: **{"Yes" if gleif_found else "No"}**
- LEI status: **{registration_status}**
- Claimed operating history: **{claimed_years} years**
- Observed footprint history: **{observed_years} years**
- Claimed workforce: **{claimed_employees}**
- Identifiable workforce: **{observed_employees}**
- OFAC name similarity: **{"N/A" if ofac_score is None else str(ofac_score)+"%"}**

**Assessment**

The current case produces **{assessment.lower()} ({score}/100)** with **{confidence.lower()} evidence confidence ({conf}/100)**. The divergence should be interpreted as a prioritisation signal for further collection, not as proof of deception, fraud, sanctions evasion, or criminality.

**Key intelligence gaps**

The highest-value next steps are to reconcile the largest footprint gaps, improve cross-source identity corroboration, establish ownership and relationship chronology, and manually resolve any sanctions-name similarity using identifiers rather than names alone.

**Recommended action**

**{recommendation}.**

**Falsification requirement**

Actively seek credible evidence that would reduce the divergence score—for example independent proof of facilities, workforce, historic activity, legitimate ownership links, or commercial operations. A senior assessment should become weaker when better evidence contradicts it.
""")

    now=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    st.markdown(f'<div class="footer">Framework: {FRAMEWORK} · Version: {VERSION} · Principal Investigator: {PI_NAME} · Generated: {now}. Public-source absence may reflect disclosure limits, jurisdictional differences, language barriers, or incomplete coverage.</div>',unsafe_allow_html=True)
