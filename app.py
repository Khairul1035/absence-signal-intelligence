
import os
import re
import streamlit as st
import pandas as pd
import requests
from io import StringIO
from datetime import datetime, timezone
from rapidfuzz import fuzz, process
import plotly.graph_objects as go
import plotly.express as px

st.set_page_config(
    page_title="The Absence Signal | Flagship Intelligence Workbench",
    page_icon="◌",
    layout="wide",
    initial_sidebar_state="expanded"
)

PI_NAME = "Mohd Khairul Ridhuan bin Mohd Fadzil"
VERSION = "V3.0"
FRAMEWORK = "The Absence Signal"
METHOD = "Expected Footprint Divergence + Network Coherence + Behavioural Drift"

# ---------- style ----------
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
.hero-sub {max-width:980px;color:#4B5563;font-size:1rem;line-height:1.65;margin-top:12px;}
.pi {margin-top:17px;font-size:.82rem;color:#374151;}
.card {background:#FFFFFF;border:1px solid #E5E7EB;border-radius:14px;padding:17px 19px;min-height:118px;}
.mlabel {font-size:.69rem;text-transform:uppercase;letter-spacing:.1em;font-weight:700;color:#6B7280;}
.mvalue {font-size:1.7rem;font-weight:700;color:#111827;margin-top:8px;line-height:1.1;}
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

def secret(name, default=""):
    try:
        return st.secrets.get(name, os.getenv(name, default))
    except Exception:
        return os.getenv(name, default)

@st.cache_data(ttl=1800, show_spinner=False)
def gleif_search(name):
    r = requests.get(
        "https://api.gleif.org/api/v1/lei-records",
        params={"filter[entity.legalName]": name, "page[size]": 10},
        timeout=20
    )
    r.raise_for_status()
    return r.json()

@st.cache_data(ttl=3600, show_spinner=False)
def ofac_names():
    urls = [
        "https://www.treasury.gov/ofac/downloads/sdn.csv",
        "https://sanctionslistservice.ofac.treas.gov/api/PublicationPreview/exports/SDN.CSV",
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

def ofac_screen(name):
    names = ofac_names()
    if not names:
        return "Feed unavailable", None
    try:
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
    return r.json() if r.status_code == 200 else None

@st.cache_data(ttl=1800, show_spinner=False)
def opencorporates_search(name, api_token):
    if not api_token:
        return None
    r = requests.get(
        "https://api.opencorporates.com/v0.4/companies/search",
        params={"q": name, "order": "score", "per_page": 5, "api_token": api_token},
        timeout=20
    )
    return r.json() if r.status_code == 200 else None

def safe(x, default="—"):
    return x if x not in [None, "", [], {}] else default

def sic_label(code):
    if not code:
        return "—"
    c = str(code).replace(" ", "")
    m = {
        "64191":"Banks",
        "64205":"Activities of financial services holding companies",
        "70100":"Activities of head offices",
        "62020":"Information technology consultancy",
        "62012":"Business and domestic software development",
        "62090":"Other information technology service activities",
        "46900":"Non-specialised wholesale trade",
        "49410":"Freight transport by road",
        "50200":"Sea and coastal freight water transport",
        "06100":"Extraction of crude petroleum",
        "06200":"Extraction of natural gas",
        "35110":"Production of electricity",
        "64999":"Other financial service activities",
    }
    return m.get(c, f"SIC {c}")

def calc_efd(d):
    weights = {
        "Legal identity":10,
        "Cross-source identity":10,
        "Operating history":12,
        "Workforce footprint":12,
        "Operational presence":12,
        "Market / trade activity":12,
        "Digital history":8,
        "Ownership transparency":8,
        "Overseas network visibility":8,
        "Sanctions-name cue":8,
    }
    g = {}
    g["Legal identity"] = 0 if d["source_hits"] >= 1 else 1
    g["Cross-source identity"] = 0 if d["source_hits"] >= 2 else (0.5 if d["source_hits"] == 1 else 1)
    g["Operating history"] = 0 if d["claimed_years"] == 0 else 1-min(d["observed_years"]/max(d["claimed_years"],1),1)
    g["Workforce footprint"] = 0 if d["claimed_employees"] == 0 else 1-min(d["observed_employees"]/max(d["claimed_employees"],1),1)
    g["Operational presence"] = 0 if d["physical"] else 1
    g["Market / trade activity"] = 0 if d["market"] else 1
    g["Digital history"] = 0 if d["digital"] else 1
    g["Ownership transparency"] = 0 if d["ownership"] else 1
    g["Overseas network visibility"] = 0 if d["overseas_verified"] else 1
    s = d["ofac_score"]
    g["Sanctions-name cue"] = 0 if s is None or s < 85 else (1 if s >= 95 else .5)
    score = round(sum(weights[k]*g[k] for k in weights))
    return score, weights, g

def calc_network_coherence(industry_known, overseas_count, ownership, physical, market):
    components = [
        1 if industry_known else 0,
        min(overseas_count/3,1) if overseas_count else 0,
        1 if ownership else 0,
        1 if physical else 0,
        1 if market else 0,
    ]
    return round(sum(components)/len(components)*100)

def calc_drift(changed_directors, changed_address, changed_owner, rebrand, new_overseas, short_window):
    n = sum([changed_directors, changed_address, changed_owner, rebrand, new_overseas])
    raw = n * 16 + (20 if short_window and n >= 2 else 0)
    return min(raw, 100)

def confidence(source_hits, checks):
    return round(min(source_hits/3,1)*55 + min(checks/5,1)*45)

# ---------- sidebar ----------
with st.sidebar:
    st.markdown("### Investigation Setup")
    st.caption("Search, resolve, compare, test, judge.")
    entity_name = st.text_input("Company / entity name", placeholder="e.g. HSBC HOLDINGS PLC")

    st.markdown("---")
    st.markdown("#### Claimed profile")
    claimed_years = st.number_input("Claimed years operating", 0, 200, 10)
    claimed_employees = st.number_input("Claimed employees", 0, 1_000_000, 100)
    claimed_industry = st.text_input("Claimed primary industry", placeholder="e.g. Industrial manufacturing")

    st.markdown("#### Observed footprint")
    observed_years = st.number_input("Verified footprint years", 0, 200, 3)
    observed_employees = st.number_input("Identifiable employees", 0, 1_000_000, 20)
    physical = st.checkbox("Operational presence verified")
    market = st.checkbox("Market / trade activity verified")
    digital = st.checkbox("Digital history aligns with claim")
    ownership = st.checkbox("Ownership / control sufficiently visible")
    overseas_verified = st.checkbox("Overseas network independently verified")
    overseas_text = st.text_input("Observed overseas jurisdictions", placeholder="e.g. UAE, Singapore, UK")

    st.markdown("---")
    st.markdown("#### Behavioural drift")
    changed_directors = st.checkbox("Recent director change")
    changed_address = st.checkbox("Recent address change")
    changed_owner = st.checkbox("Recent ownership/control change")
    rebrand = st.checkbox("Recent rebrand / major website shift")
    new_overseas = st.checkbox("Recent new overseas entity / branch")
    short_window = st.checkbox("2+ changes occurred in a short period")

    st.markdown("---")
    ch_key = secret("COMPANIES_HOUSE_API_KEY")
    oc_key = secret("OPENCORPORATES_API_TOKEN")
    st.caption("Companies House: " + ("connected" if ch_key else "not configured"))
    st.caption("OpenCorporates: " + ("connected" if oc_key else "not configured"))

    run = st.button("Run intelligence assessment", type="primary", use_container_width=True)

# ---------- header ----------
st.markdown(f"""
<div class="hero">
  <div class="kicker">Corporate Ecosystem & Counterparty Intelligence · {VERSION}</div>
  <div class="hero-title">{FRAMEWORK}</div>
  <div class="hero-sub">
    A public-source intelligence workbench that explains who a company is, what it does, where it operates,
    who it connects to, what has changed, what does not fit, and what an investigator should verify next.
  </div>
  <div class="pi"><b>Principal Investigator:</b> {PI_NAME}</div>
</div>
""", unsafe_allow_html=True)

if not run:
    cols = st.columns(5)
    cards = [
        ("01 · Understand","Company","What is it and what does it do?"),
        ("02 · Map","Ecosystem","Which industries and countries connect to it?"),
        ("03 · Compare","Reality","Does observable reality support the claims?"),
        ("04 · Detect","Change","What changed before the current picture emerged?"),
        ("05 · Judge","So what?","What matters and what should be checked next?")
    ]
    for c,(a,b,n) in zip(cols,cards):
        with c:
            st.markdown(f'<div class="card"><div class="mlabel">{a}</div><div class="mvalue">{b}</div><div class="mnote">{n}</div></div>', unsafe_allow_html=True)
    st.markdown('<div class="dark"><h2>Understand the company. Then look for what does not fit.</h2><p>The workbench is designed to turn fragmented public-source data into a decision-oriented intelligence brief.</p></div>', unsafe_allow_html=True)
    st.stop()

if not entity_name.strip():
    st.error("Enter a company or entity name.")
    st.stop()

# ---------- collection ----------
with st.spinner("Resolving company and collecting current public-source signals..."):
    gleif_found=False; legal_name=entity_name.strip(); lei="—"; jurisdiction="—"; address="—"; lei_status="Not located"
    try:
        g=gleif_search(entity_name.strip())
        recs=g.get("data",[])
        if recs:
            rec=recs[0]; attrs=rec.get("attributes",{}); ent=attrs.get("entity",{}); reg=attrs.get("registration",{})
            gleif_found=True
            legal_name=safe(ent.get("legalName",{}).get("name"),entity_name.strip())
            lei=safe(attrs.get("lei")); jurisdiction=safe(ent.get("jurisdiction"))
            ad=ent.get("legalAddress",{})
            parts=[]
            if ad.get("addressLines"): parts += ad["addressLines"]
            for k in ["city","region","country"]:
                if ad.get(k): parts.append(ad[k])
            address=", ".join(parts) if parts else "—"
            lei_status=safe(reg.get("status"))
    except Exception:
        pass

    ch=companies_house_search(entity_name.strip(), ch_key)
    ch_item=(ch.get("items") or [None])[0] if ch else None

    oc=opencorporates_search(entity_name.strip(), oc_key)
    oc_company=None
    try:
        arr=oc["results"]["companies"] if oc else []
        if arr: oc_company=arr[0]["company"]
    except Exception:
        pass

    ofac_match, ofac_score=ofac_screen(legal_name)

# ---------- enrich snapshot ----------
sources=[]
industry_labels=[]
country_nodes=set()
if gleif_found:
    sources.append(("GLEIF", legal_name, jurisdiction, lei, "LEI reference"))
    if jurisdiction != "—": country_nodes.add(str(jurisdiction))
if ch_item:
    sources.append(("Companies House", safe(ch_item.get("title")), "United Kingdom", safe(ch_item.get("company_number")), "Official UK register"))
    for code in ch_item.get("sic_codes",[]) or []:
        industry_labels.append(sic_label(code))
    country_nodes.add("United Kingdom")
if oc_company:
    sources.append(("OpenCorporates", safe(oc_company.get("name")), safe(oc_company.get("jurisdiction_code")), safe(oc_company.get("company_number")), "Corporate data aggregation"))
    if oc_company.get("jurisdiction_code"): country_nodes.add(str(oc_company.get("jurisdiction_code")))
    for ic in oc_company.get("industry_codes",[]) or []:
        desc = ic.get("description") or ic.get("industry_code") or ic.get("code")
        if desc: industry_labels.append(str(desc))
    if oc_company.get("home_company"):
        hc=oc_company["home_company"]
        if hc.get("jurisdiction_code"): country_nodes.add(str(hc.get("jurisdiction_code")))

manual_countries=[x.strip() for x in re.split(r"[,;]", overseas_text) if x.strip()]
for x in manual_countries: country_nodes.add(x)

primary_industry = industry_labels[0] if industry_labels else (claimed_industry if claimed_industry else "Not independently resolved")
adjacent_industries = list(dict.fromkeys(industry_labels[1:5])) if len(industry_labels)>1 else []

source_hits=len(sources)
verified_checks=sum([physical,market,digital,ownership,overseas_verified])
efd, weights, gaps=calc_efd({
    "source_hits":source_hits,"claimed_years":claimed_years,"observed_years":observed_years,
    "claimed_employees":claimed_employees,"observed_employees":observed_employees,
    "physical":physical,"market":market,"digital":digital,"ownership":ownership,
    "overseas_verified":overseas_verified,"ofac_score":ofac_score
})
network=calc_network_coherence(primary_industry!="Not independently resolved", len(country_nodes), ownership, physical, market)
drift=calc_drift(changed_directors,changed_address,changed_owner,rebrand,new_overseas,short_window)
conf=confidence(source_hits,verified_checks)

efd_class="HIGH" if efd>=70 else ("MODERATE" if efd>=40 else "LOW")
conf_class="HIGH" if conf>=75 else ("MODERATE" if conf>=45 else "LOW")
drift_class="ELEVATED" if drift>=60 else ("WATCH" if drift>=30 else "LOW")

# ---------- main ----------
tabs=st.tabs([
    "20-Second Snapshot","Industry & Overseas","What Doesn't Fit?",
    "Behavioural Drift","Evidence & Network","Analyst Brief"
])

with tabs[0]:
    st.markdown('<div class="section">Company intelligence snapshot</div>', unsafe_allow_html=True)
    st.markdown(f"## {legal_name}")
    st.caption(f"{primary_industry} · {jurisdiction} · LEI status: {lei_status}")

    cols=st.columns(5)
    metrics=[
        ("Primary Industry",primary_industry[:28],"Current best resolved classification"),
        ("Jurisdictions",str(len(country_nodes)),"Observed / resolved network locations"),
        ("EFD",f"{efd}/100",f"{efd_class} divergence"),
        ("Network Coherence",f"{network}/100","Does the ecosystem make sense?"),
        ("Behavioural Drift",f"{drift}/100",f"{drift_class} change signal"),
    ]
    for c,(a,b,n) in zip(cols,metrics):
        with c:
            st.markdown(f'<div class="card"><div class="mlabel">{a}</div><div class="mvalue">{b}</div><div class="mnote">{n}</div></div>', unsafe_allow_html=True)

    if efd>=70:
        one_liner="The observable operating footprint is materially thinner than the profile currently being tested."
    elif efd>=40:
        one_liner="Several elements of the stated profile require additional corroboration before reliance."
    else:
        one_liner="The observable footprint is broadly consistent with the profile currently being tested."

    st.markdown(f'<div class="dark"><div class="kicker" style="color:#9CA3AF">What matters most</div><h2>{one_liner}</h2><p>Evidence confidence is <b>{conf_class.lower()}</b> ({conf}/100). Behavioural drift is <b>{drift_class.lower()}</b>. The dashboard prioritises verification rather than making allegations.</p></div>', unsafe_allow_html=True)

    c1,c2=st.columns([1.15,.85])
    with c1:
        st.markdown("#### Identity")
        st.dataframe(pd.DataFrame([
            ["Legal name",legal_name],
            ["LEI",lei],
            ["Jurisdiction",jurisdiction],
            ["Address",address],
            ["Primary industry",primary_industry],
            ["Resolved sources",source_hits],
            ["Closest OFAC SDN name",ofac_match],
        ],columns=["Field","Observed"]),use_container_width=True,hide_index=True)
    with c2:
        st.markdown("#### What should I know?")
        bullets=[
            f"Identity is {'corroborated across multiple sources' if source_hits>=2 else 'supported by one or fewer configured sources'}.",
            f"Industry is {primary_industry}.",
            f"Observed jurisdictional footprint currently spans {len(country_nodes)} location(s).",
            f"Expected Footprint Divergence is {efd}/100.",
            f"Behavioural Drift is {drift}/100."
        ]
        for b in bullets:
            st.markdown(f'<div class="callout">{b}</div>',unsafe_allow_html=True)

with tabs[1]:
    st.markdown('<div class="section">Industry ecosystem</div>', unsafe_allow_html=True)
    st.markdown(f"**Primary industry:** {primary_industry}")
    if adjacent_industries:
        st.markdown("**Adjacent / additional resolved industries:** " + ", ".join(adjacent_industries))
    else:
        st.caption("No additional industry codes were resolved from the configured live sources.")

    st.markdown('<div class="section">Overseas network</div>', unsafe_allow_html=True)
    if country_nodes:
        country_df=pd.DataFrame({"Jurisdiction / market":sorted(country_nodes)})
        st.dataframe(country_df,use_container_width=True,hide_index=True)
    else:
        st.warning("No overseas or jurisdictional network has yet been resolved.")

    st.markdown("#### Network interpretation")
    if len(country_nodes)>=3:
        st.success("The company presents a multi-jurisdiction footprint. The next question is whether those links are operationally coherent with its business model.")
    elif len(country_nodes)==2:
        st.info("A cross-border footprint is visible, but additional relationship-level verification would improve the network picture.")
    else:
        st.info("The current footprint appears concentrated in one jurisdiction or is under-observed.")

    st.markdown("#### Network coherence questions")
    qs=[
        "Do the countries in the network make sense for the company's business model?",
        "Do subsidiaries, branches, parents, suppliers or counterparties cluster in expected industries?",
        "Are any overseas links newly created relative to major contracts, financing or ownership changes?",
        "Does the legal network match the operational network?",
        "Is the observed network broader, narrower or simply different from the public narrative?"
    ]
    for q in qs:
        st.markdown(f'<div class="callout">{q}</div>',unsafe_allow_html=True)

with tabs[2]:
    st.markdown('<div class="section">Expected Footprint Divergence</div>', unsafe_allow_html=True)
    rows=[{"Dimension":k,"Weight":w,"Gap severity":round(gaps[k],2),"Contribution":round(w*gaps[k],1)} for k,w in weights.items()]
    df=pd.DataFrame(rows).sort_values("Contribution",ascending=False)
    fig=go.Figure(go.Bar(x=df["Contribution"],y=df["Dimension"],orientation="h",marker_color="#111827",text=df["Contribution"],textposition="outside"))
    fig.update_layout(height=440,xaxis_title="Contribution to divergence score",yaxis_title="",margin=dict(l=10,r=20,t=20,b=10),paper_bgcolor="white",plot_bgcolor="white",font={'family':'Inter'},yaxis={'categoryorder':'total ascending'},showlegend=False)
    st.plotly_chart(fig,use_container_width=True,config={'displayModeBar':False})
    st.dataframe(df,use_container_width=True,hide_index=True)

    st.markdown("#### So what?")
    top=df[df["Contribution"]>0].head(3)["Dimension"].tolist()
    if top:
        st.markdown(f"The current assessment is driven primarily by **{', '.join(top)}**. These are the highest-value verification priorities.")
    else:
        st.success("No material footprint mismatch was captured in the current assessment.")

with tabs[3]:
    st.markdown('<div class="section">Corporate Behavioural Drift</div>', unsafe_allow_html=True)
    st.markdown(f"### Drift score: {drift}/100 · {drift_class}")

    changes=[]
    mapping=[
        ("Director change",changed_directors),
        ("Address change",changed_address),
        ("Ownership/control change",changed_owner),
        ("Rebrand / major website shift",rebrand),
        ("New overseas entity / branch",new_overseas),
    ]
    for label,flag in mapping:
        if flag: changes.append(label)

    if changes:
        years=list(range(datetime.now().year-len(changes)+1,datetime.now().year+1))
        tdf=pd.DataFrame({"Event":changes,"Sequence":range(1,len(changes)+1),"Year":years[-len(changes):]})
        fig=px.scatter(tdf,x="Sequence",y=[1]*len(tdf),text="Event",size=[20]*len(tdf))
        fig.update_traces(textposition="top center")
        fig.update_layout(height=300,yaxis_visible=False,xaxis_title="Observed change sequence",showlegend=False,paper_bgcolor="white",plot_bgcolor="white",font={'family':'Inter'})
        st.plotly_chart(fig,use_container_width=True,config={'displayModeBar':False})
    else:
        st.info("No behavioural changes were marked in the current investigation.")

    st.markdown("#### Why this matters")
    st.markdown("A company can look normal in a static snapshot while changing rapidly underneath. The relevant question is not only **what the company is**, but **what it may be becoming**.")

with tabs[4]:
    st.markdown('<div class="section">Evidence ledger</div>', unsafe_allow_html=True)
    ledger=pd.DataFrame([
        ["Legal identity","Configured registries","Resolved" if source_hits else "Unresolved","High" if source_hits>=2 else "Moderate" if source_hits==1 else "Low"],
        ["Industry","Registry SIC / industry codes / claim",primary_industry,"Moderate" if industry_labels else "Low"],
        ["Operating history","Observed chronology",f"{observed_years} of {claimed_years} claimed years","Moderate"],
        ["Workforce","Observed public footprint",f"{observed_employees} of {claimed_employees} claimed","Moderate"],
        ["Operational presence","Public-source verification","Verified" if physical else "Not verified","Moderate"],
        ["Market activity","Public-source verification","Verified" if market else "Not verified","Moderate"],
        ["Ownership","Corporate/network sources","Adequate" if ownership else "Incomplete","Moderate"],
        ["Overseas network","Registry/network sources",f"{len(country_nodes)} location(s)","Moderate" if overseas_verified else "Low"],
        ["Sanctions-name cue","OFAC SDN","N/A" if ofac_score is None else f"{ofac_score}% similarity","Low until identifiers checked"],
    ],columns=["Question","Source / method","Finding","Confidence"])
    st.dataframe(ledger,use_container_width=True,hide_index=True)

    st.markdown('<div class="section">Entity resolution</div>', unsafe_allow_html=True)
    if sources:
        st.dataframe(pd.DataFrame(sources,columns=["Source","Resolved name","Jurisdiction","Identifier","Role"]),use_container_width=True,hide_index=True)
    else:
        st.warning("No configured source returned a usable entity match.")

    st.markdown("#### Falsification discipline")
    st.info("Actively seek evidence that would reduce the divergence or drift assessment. Strong intelligence work should become weaker when better evidence contradicts the hypothesis.")

with tabs[5]:
    st.markdown('<div class="section">Executive analyst brief</div>', unsafe_allow_html=True)
    rec = "Escalate for enhanced due diligence." if efd>=70 else ("Resolve priority gaps before reliance." if efd>=40 else "No major inconsistency captured; continue proportionate monitoring.")
    st.markdown(f"""
**Principal Investigator:** {PI_NAME}

**Question**

Does **{legal_name}** look, operate and connect in a way that is consistent with the organisation it claims to be?

**Company**

Current best industry classification: **{primary_industry}**.  
Resolved jurisdictional / overseas footprint: **{len(country_nodes)} location(s)**.  
Independent entity sources returning a usable match: **{source_hits}**.

**Assessment**

Expected Footprint Divergence: **{efd}/100 ({efd_class})**.  
Network Coherence: **{network}/100**.  
Behavioural Drift: **{drift}/100 ({drift_class})**.  
Evidence Confidence: **{conf}/100 ({conf_class})**.

**So what?**

The value of this assessment is not to label the entity as “good” or “bad”. It is to identify where the company's claimed reality, operating footprint, network structure and recent behaviour do not yet reconcile—and to focus investigative effort on those gaps.

**Practical implication**

**{rec}**

**Next collection priorities**

1. Reconcile the highest-contributing EFD dimensions.
2. Validate industry and overseas-network relationships using independent sources.
3. Resolve ownership/control and relationship chronology.
4. Test whether recent corporate changes cluster around major commercial or financing events.
5. Seek falsifying evidence that could materially reduce the current assessment.

**Analytic caveat**

Absence can reflect disclosure limits, language barriers, registry coverage or genuinely private operations. Name similarity is not identity. Network proximity is not culpability. Every escalation should be identifier-led and evidence-led.
""")

    now=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    st.markdown(f'<div class="footer">{FRAMEWORK} · {METHOD} · {VERSION} · Principal Investigator: {PI_NAME} · Generated {now}</div>',unsafe_allow_html=True)
