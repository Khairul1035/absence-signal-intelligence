
import math
import requests
import pandas as pd
import numpy as np
import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timezone

st.set_page_config(
    page_title="SOCIAL LOAD | AI Infrastructure Stability Monitor",
    page_icon="◌",
    layout="wide",
    initial_sidebar_state="expanded"
)

PI = "Mohd Khairul Ridhuan bin Mohd Fadzil"
VERSION = "V1.0"

# -----------------------------
# STYLE
# -----------------------------
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
html, body, [class*="css"] {font-family:'Inter', sans-serif;}
.stApp {background:#F5F6F8;color:#111827;}
.block-container {padding-top:1.15rem;padding-bottom:3rem;max-width:1520px;}
section[data-testid="stSidebar"] {background:#FFFFFF;border-right:1px solid #E5E7EB;}
h1,h2,h3 {letter-spacing:-.03em;color:#111827;}
.hero {background:#FFFFFF;border:1px solid #E5E7EB;border-radius:18px;padding:29px 31px;margin-bottom:16px;}
.kicker {font-size:.70rem;font-weight:700;text-transform:uppercase;letter-spacing:.14em;color:#6B7280;}
.hero-title {font-size:2.6rem;line-height:1.03;font-weight:700;margin:5px 0 0 0;color:#111827;}
.hero-sub {font-size:1rem;color:#4B5563;line-height:1.65;margin-top:12px;max-width:980px;}
.pi {margin-top:17px;font-size:.82rem;color:#374151;}
.card {background:#FFFFFF;border:1px solid #E5E7EB;border-radius:14px;padding:17px 19px;min-height:119px;}
.mlabel {font-size:.68rem;text-transform:uppercase;letter-spacing:.10em;font-weight:700;color:#6B7280;}
.mvalue {font-size:1.82rem;font-weight:700;line-height:1.08;margin-top:8px;color:#111827;}
.mnote {font-size:.79rem;color:#6B7280;margin-top:7px;}
.dark {background:#111827;color:#FFFFFF;border-radius:16px;padding:24px 26px;margin:14px 0;}
.dark h2 {color:#FFFFFF;font-size:1.8rem;margin:0;}
.dark p {color:#D1D5DB;line-height:1.6;margin:8px 0 0 0;}
.section {font-size:1.06rem;font-weight:700;margin:9px 0 10px 0;}
.callout {background:#FFFFFF;border-left:4px solid #111827;border-top:1px solid #E5E7EB;border-right:1px solid #E5E7EB;border-bottom:1px solid #E5E7EB;border-radius:10px;padding:14px 16px;margin:7px 0;}
.micro {font-size:.76rem;color:#6B7280;line-height:1.55;}
.footer {font-size:.72rem;color:#6B7280;margin-top:24px;line-height:1.6;}
.stButton>button {border-radius:10px;font-weight:600;}
</style>
""", unsafe_allow_html=True)

# -----------------------------
# BENCHMARKS / HUBS
# -----------------------------
HUBS = {
    "Johor, Malaysia": {"iso":"MYS","mw":850,"water":72,"tariff":48,"opposition":38,"trust":52,"heat":74,"media":45},
    "Singapore": {"iso":"SGP","mw":900,"water":84,"tariff":62,"opposition":54,"trust":72,"heat":77,"media":67},
    "Northern Virginia, USA": {"iso":"USA","mw":3200,"water":46,"tariff":63,"opposition":72,"trust":45,"heat":43,"media":82},
    "Dublin, Ireland": {"iso":"IRL","mw":1100,"water":36,"tariff":71,"opposition":76,"trust":61,"heat":22,"media":78},
    "Frankfurt, Germany": {"iso":"DEU","mw":1200,"water":35,"tariff":69,"opposition":58,"trust":60,"heat":28,"media":63},
    "Amsterdam, Netherlands": {"iso":"NLD","mw":950,"water":32,"tariff":66,"opposition":73,"trust":64,"heat":25,"media":70},
    "Sydney, Australia": {"iso":"AUS","mw":1000,"water":61,"tariff":59,"opposition":49,"trust":58,"heat":56,"media":55},
}
# Values above are scenario baselines for modelling, not claims of measured real-world scores.

IEA_STATS = {
    "2024 data-centre electricity": "460 TWh",
    "2030 projected electricity": "~945 TWh",
    "2024–2030 growth": "~15% p.a.",
    "SE Asia outlook": ">2× by 2030",
}

WB_INDICATORS = {
    "ER.H2O.FWST.ZS": "Water stress",
    "PV.EST": "Political stability",
    "SP.URB.TOTL.IN.ZS": "Urban population",
    "EN.POP.DNST": "Population density",
    "EG.ELC.LOSS.ZS": "T&D electricity losses",
    "EG.ELC.RNEW.ZS": "Renewable electricity output",
}

@st.cache_data(ttl=21600, show_spinner=False)
def wb_latest(iso, indicator):
    url=f"https://api.worldbank.org/v2/country/{iso}/indicator/{indicator}"
    try:
        r=requests.get(url,params={"format":"json","mrnev":1,"per_page":5},timeout=15)
        r.raise_for_status()
        js=r.json()
        if len(js)>1 and js[1]:
            row=js[1][0]
            return row.get("value"), row.get("date")
    except Exception:
        pass
    return None, None

@st.cache_data(ttl=1800, show_spinner=False)
def gdelt_attention(query):
    # Best-effort public media-attention signal. Failure does not block the app.
    try:
        url="https://api.gdeltproject.org/api/v2/doc/doc"
        params={
            "query":query,
            "mode":"artlist",
            "format":"json",
            "maxrecords":75,
            "timespan":"30d",
            "sort":"datedesc"
        }
        r=requests.get(url,params=params,timeout=20,headers={"User-Agent":"Mozilla/5.0"})
        if r.ok and "json" in r.headers.get("content-type",""):
            js=r.json()
            arts=js.get("articles",[])
            return len(arts), arts[:5]
    except Exception:
        pass
    return None, []

def clip(x): return max(0,min(100,float(x)))

def norm_mw(mw):
    # Compression: 100 MW is material, 3,000+ MW is extreme cluster-scale load.
    return clip((math.log10(max(mw,10))-1)*50)

def inv_political_stability(v):
    # WGI PV.EST roughly -2.5 to +2.5. Convert lower stability to higher pressure.
    if v is None: return None
    return clip((2.5-float(v))/5*100)

def normalize_water(v):
    if v is None: return None
    # 100% withdrawals / available resource = severe structural stress marker.
    return clip(float(v))

def normalize_density(v):
    if v is None: return None
    # log compression for wide cross-country range
    return clip((math.log10(max(float(v),1))/4)*100)

def normalize_losses(v):
    if v is None: return None
    return clip(float(v)*5)

def weighted(parts):
    vals=[(v,w) for v,w in parts if v is not None]
    if not vals: return 0
    return round(sum(v*w for v,w in vals)/sum(w for _,w in vals),1)

def percentile(value, series):
    a=np.array(series,dtype=float)
    return int(round((a < value).mean()*100))

def compute_indices(mw, water, tariff, opposition, trust, heat, political_inv, density, losses, media):
    infrastructure = weighted([
        (norm_mw(mw),0.28),
        (water,0.24),
        (tariff,0.18),
        (heat,0.12),
        (losses,0.10),
        (density,0.08),
    ])
    friction = weighted([
        (opposition,0.34),
        (tariff,0.20),
        (media,0.16),
        (100-trust,0.15),
        (political_inv,0.15),
    ])
    # Cognitive pressure is explicitly a population-level proxy, not a clinical measure.
    cognitive = weighted([
        (friction,0.35),
        (heat,0.18),
        (tariff,0.18),
        (water,0.14),
        (100-trust,0.15),
    ])
    social_load = weighted([
        (infrastructure,0.44),
        (friction,0.36),
        (cognitive,0.20),
    ])
    return infrastructure, friction, cognitive, social_load

def label(v):
    if v >= 75: return "CRITICAL"
    if v >= 60: return "HIGH"
    if v >= 40: return "ELEVATED"
    return "MANAGEABLE"

def implication(v):
    if v >= 75: return "Pause acceleration; mitigation and stakeholder strategy should precede further load growth."
    if v >= 60: return "Expansion remains possible, but social and infrastructure mitigation should be treated as a gating condition."
    if v >= 40: return "Pressure is visible. Targeted mitigation and tighter monitoring are warranted."
    return "No immediate systemic pressure signal; maintain proportional monitoring."

# -----------------------------
# SIDEBAR
# -----------------------------
with st.sidebar:
    st.markdown("### Scenario Setup")
    hub=st.selectbox("Data-centre hub",list(HUBS.keys()))
    base=HUBS[hub]

    st.markdown("---")
    st.markdown("#### Infrastructure")
    mw=st.number_input("Estimated / planned data-centre load (MW)",0,10000,int(base["mw"]),50)
    water=st.slider("Local water sensitivity",0,100,int(base["water"]))
    tariff=st.slider("Household / tariff pressure",0,100,int(base["tariff"]))
    heat=st.slider("Heat / cooling pressure",0,100,int(base["heat"]))

    st.markdown("#### Community")
    opposition=st.slider("Planning / community opposition",0,100,int(base["opposition"]))
    trust=st.slider("Institutional trust / perceived fairness",0,100,int(base["trust"]))
    media_manual=st.slider("Media / political attention",0,100,int(base["media"]))

    st.markdown("---")
    st.caption("Local sliders are analyst scenario inputs. World Bank indicators are retrieved live where available.")
    run=st.button("Run stability assessment",type="primary",use_container_width=True)

# -----------------------------
# HERO
# -----------------------------
st.markdown(f"""
<div class="hero">
 <div class="kicker">AI Infrastructure Stability Intelligence · {VERSION}</div>
 <div class="hero-title">SOCIAL LOAD</div>
 <div class="hero-sub">
   Measures when rapid AI-infrastructure expansion may begin to exceed a location's infrastructure capacity,
   community tolerance and population-level pressure resilience. The objective is early warning—not prediction of unrest.
 </div>
 <div class="pi"><b>Principal Investigator:</b> {PI}</div>
</div>
""",unsafe_allow_html=True)

if not run:
    c1,c2,c3,c4=st.columns(4)
    cards=[
        ("01 · Load","Infrastructure","How much pressure enters the system?"),
        ("02 · Friction","Community","How much resistance is already visible?"),
        ("03 · Perception","Cognitive Proxy","Do stressors reinforce threat and fairness concerns?"),
        ("04 · Decision","Social Load","Can the community absorb further expansion?")
    ]
    for c,(a,b,n) in zip([c1,c2,c3,c4],cards):
        with c:
            st.markdown(f'<div class="card"><div class="mlabel">{a}</div><div class="mvalue">{b}</div><div class="mnote">{n}</div></div>',unsafe_allow_html=True)
    st.markdown('<div class="dark"><h2>A grid can carry the megawatts. Can the community carry the consequences?</h2><p>SOCIAL LOAD connects physical infrastructure pressure with public-friction and cognitive-pressure proxies to support site-selection, policy and early-warning decisions.</p></div>',unsafe_allow_html=True)
    st.stop()

# -----------------------------
# LIVE DATA
# -----------------------------
iso=base["iso"]
live={}
for code,name in WB_INDICATORS.items():
    live[code]=wb_latest(iso,code)

wb_water=normalize_water(live["ER.H2O.FWST.ZS"][0])
political_inv=inv_political_stability(live["PV.EST"][0])
density=normalize_density(live["EN.POP.DNST"][0])
losses=normalize_losses(live["EG.ELC.LOSS.ZS"][0])

media_count, media_articles=gdelt_attention(f'"data center" {hub.split(",")[0]}')
media_signal=media_manual if media_count is None else clip(media_manual*0.55 + min(media_count/75*100,100)*0.45)

infra, friction, cognitive, social=compute_indices(
    mw=mw, water=water if wb_water is None else weighted([(water,.55),(wb_water,.45)]),
    tariff=tariff, opposition=opposition, trust=trust, heat=heat,
    political_inv=political_inv, density=density, losses=losses, media=media_signal
)

# benchmark all hubs using their defaults for percentile comparison
bench=[]
for h,b in HUBS.items():
    vals=compute_indices(b["mw"],b["water"],b["tariff"],b["opposition"],b["trust"],b["heat"],50,50,25,b["media"])
    bench.append((h,*vals))
bench_df=pd.DataFrame(bench,columns=["Hub","Infrastructure","Friction","Cognitive","Social Load"])
pctl=percentile(social,bench_df["Social Load"])

# scenario analysis
scenarios=[]
for name,mult,opp_delta,tariff_delta in [
    ("Current",1.0,0,0),
    ("+25% capacity",1.25,5,4),
    ("+50% capacity",1.50,10,8),
    ("Mitigation case",1.25,-15,-10),
]:
    vals=compute_indices(
        mw*mult,
        water,
        clip(tariff+tariff_delta),
        clip(opposition+opp_delta),
        trust,
        heat,
        political_inv,density,losses,media_signal
    )
    scenarios.append([name,round(mw*mult),*vals])
scenario_df=pd.DataFrame(scenarios,columns=["Scenario","MW","Infrastructure","Friction","Cognitive","Social Load"])

# -----------------------------
# TABS
# -----------------------------
tabs=st.tabs(["20-Second Brief","Statistics","Pressure Anatomy","Scenario Stress-Test","Evidence & Method","Analyst Brief"])

with tabs[0]:
    st.markdown(f"## {hub}")
    st.caption(f"AI infrastructure stability assessment · country code {iso}")

    cols=st.columns(5)
    metrics=[
        ("Social Load",f"{social:.0f}/100",label(social)),
        ("Infrastructure",f"{infra:.0f}/100",label(infra)),
        ("Community Friction",f"{friction:.0f}/100",label(friction)),
        ("Cognitive Proxy",f"{cognitive:.0f}/100",label(cognitive)),
        ("Hub Percentile",f"{pctl}th","vs modelled peer hubs"),
    ]
    for c,(a,b,n) in zip(cols,metrics):
        with c:
            st.markdown(f'<div class="card"><div class="mlabel">{a}</div><div class="mvalue">{b}</div><div class="mnote">{n}</div></div>',unsafe_allow_html=True)

    st.markdown(f'<div class="dark"><div class="kicker" style="color:#9CA3AF">Executive judgement</div><h2>{label(social)} SOCIAL LOAD</h2><p>{implication(social)} The dominant pressure channels are identified below; this is an early-warning assessment, not a forecast of protest or disorder.</p></div>',unsafe_allow_html=True)

    drivers=pd.DataFrame({
        "Driver":["MW load","Water sensitivity","Tariff pressure","Community opposition","Trust deficit","Heat pressure","Media attention"],
        "Score":[norm_mw(mw),water,tariff,opposition,100-trust,heat,media_signal]
    }).sort_values("Score",ascending=False)
    st.markdown("#### What matters most")
    for _,r in drivers.head(3).iterrows():
        st.markdown(f'<div class="callout"><b>{r["Driver"]}</b><br><span class="micro">{r["Score"]:.0f}/100 · material contributor to current pressure picture</span></div>',unsafe_allow_html=True)

with tabs[1]:
    st.markdown('<div class="section">Global context</div>',unsafe_allow_html=True)
    c1,c2,c3,c4=st.columns(4)
    stats=[
        ("2024 DC electricity","460 TWh","IEA global estimate"),
        ("2030 projection","~945 TWh","IEA base case"),
        ("Growth rate","~15% p.a.","2024–2030"),
        ("Southeast Asia",">2×","electricity demand by 2030")
    ]
    for c,(a,b,n) in zip([c1,c2,c3,c4],stats):
        with c:
            st.markdown(f'<div class="card"><div class="mlabel">{a}</div><div class="mvalue">{b}</div><div class="mnote">{n}</div></div>',unsafe_allow_html=True)

    st.markdown('<div class="section">Peer-hub comparison</div>',unsafe_allow_html=True)
    compare=bench_df.sort_values("Social Load",ascending=False)
    fig=px.bar(compare,x="Social Load",y="Hub",orientation="h",text="Social Load")
    fig.update_layout(height=430,showlegend=False,paper_bgcolor="white",plot_bgcolor="white",font={'family':'Inter'},yaxis={'categoryorder':'total ascending'},margin=dict(l=10,r=20,t=20,b=10))
    st.plotly_chart(fig,use_container_width=True,config={'displayModeBar':False})

    st.markdown('<div class="section">Live country indicators</div>',unsafe_allow_html=True)
    rows=[]
    for code,name in WB_INDICATORS.items():
        value,year=live[code]
        rows.append([name,"—" if value is None else round(value,2),year or "—",code])
    st.dataframe(pd.DataFrame(rows,columns=["Indicator","Latest value","Year","World Bank code"]),use_container_width=True,hide_index=True)

with tabs[2]:
    st.markdown('<div class="section">Pressure anatomy</div>',unsafe_allow_html=True)
    radar_labels=["Infrastructure","Community friction","Cognitive proxy","Water","Tariff","Opposition"]
    radar_vals=[infra,friction,cognitive,water,tariff,opposition]
    fig=go.Figure(data=go.Scatterpolar(r=radar_vals+[radar_vals[0]],theta=radar_labels+[radar_labels[0]],fill='toself'))
    fig.update_layout(polar=dict(radialaxis=dict(visible=True,range=[0,100])),showlegend=False,height=430,paper_bgcolor="white",font={'family':'Inter'})
    st.plotly_chart(fig,use_container_width=True,config={'displayModeBar':False})

    st.markdown("#### System logic")
    st.markdown("""
**Infrastructure Load** asks whether physical demand is becoming difficult to absorb.

**Community Friction** asks whether cost, opposition, trust and political attention are already creating resistance.

**Cognitive Pressure Proxy** captures population-level stressors that may intensify perceptions of threat, unfairness or uncertainty. It is **not** a neuroscience diagnosis or individual behavioural prediction.

**Social Load** combines the three into a decision-oriented early-warning indicator.
""")

with tabs[3]:
    st.markdown('<div class="section">Capacity stress-test</div>',unsafe_allow_html=True)
    fig=px.line(scenario_df,x="MW",y="Social Load",text="Scenario",markers=True)
    fig.update_traces(textposition="top center")
    fig.update_layout(height=400,paper_bgcolor="white",plot_bgcolor="white",font={'family':'Inter'},yaxis_range=[0,100])
    st.plotly_chart(fig,use_container_width=True,config={'displayModeBar':False})
    st.dataframe(scenario_df,use_container_width=True,hide_index=True)

    current=scenario_df.iloc[0]["Social Load"]
    expansion=scenario_df.iloc[1]["Social Load"]
    mitigated=scenario_df.iloc[3]["Social Load"]
    st.markdown(f"""
#### Decision implication

A **25% capacity increase** moves the model from **{current:.1f}** to **{expansion:.1f}** Social Load points under the current assumptions.

With the same capacity increase but lower tariff/community pressure, the **mitigation case falls to {mitigated:.1f}**.

The practical question therefore becomes:

> **What mitigation buys the most additional infrastructure capacity before social pressure crosses the next threshold?**
""")

with tabs[4]:
    st.markdown('<div class="section">Evidence ledger</div>',unsafe_allow_html=True)
    evidence=pd.DataFrame([
        ["Data-centre electricity benchmark","IEA","Global / regional benchmark","High","External fact"],
        ["Water stress","World Bank WDI","Country-level latest available","High if available","External indicator"],
        ["Political stability","World Bank WGI","Country-level latest available","High if available","External indicator"],
        ["Population density","World Bank WDI","Country-level latest available","High if available","External indicator"],
        ["Media attention","GDELT","Last 30 days, best-effort","Moderate","Dynamic signal"],
        ["MW load","Analyst scenario input","Project / cluster level","Depends on source","Scenario input"],
        ["Community opposition","Analyst scenario input","Local","Moderate until sourced","Proxy"],
        ["Institutional trust","Analyst scenario input","Local","Moderate until sourced","Proxy"],
    ],columns=["Variable","Source","Level","Confidence","Role"])
    st.dataframe(evidence,use_container_width=True,hide_index=True)

    st.markdown("#### Statistical discipline")
    st.markdown("""
- **Percentile** compares the current Social Load score with the modelled peer-hub baseline.
- **Scenario analysis** tests sensitivity to capacity growth and mitigation rather than pretending to forecast one deterministic future.
- **Country indicators** are contextual priors; they should not substitute for municipal-level evidence.
- **Cognitive Pressure** is a proxy constructed from observable stressors. It must never be interpreted as a clinical or individual-level measure.
- **Score thresholds are analyst-designed decision bands**, not empirically validated probabilities of unrest.
""")
    if media_count is not None:
        st.caption(f"GDELT query returned {media_count} recent matching articles (capped by query settings).")

with tabs[5]:
    top3=", ".join(drivers.head(3)["Driver"].tolist())
    st.markdown('<div class="section">Executive analyst brief</div>',unsafe_allow_html=True)
    st.markdown(f"""
**Principal Investigator:** {PI}

**Intelligence question**

Can **{hub}** absorb further AI-data-centre expansion without infrastructure pressure becoming a material source of community and political friction?

**Current assessment**

Social Load is **{social:.1f}/100 ({label(social)})**, placing the hub around the **{pctl}th percentile** of the modelled peer set. Infrastructure Pressure is **{infra:.1f}**, Community Friction **{friction:.1f}**, and the Cognitive Pressure Proxy **{cognitive:.1f}**.

**What is driving the result?**

The strongest current signals are **{top3}**.

**So what?**

The intelligence value is not the score itself. It is the ability to identify **which constraint is becoming binding first**—grid/load, water, affordability, public opposition, trust or political attention—and therefore which intervention can preserve the greatest amount of infrastructure headroom.

**Practical action**

{implication(social)}

**Collection priorities**

1. Replace scenario inputs with municipal-level electricity, water, tariff and planning data.
2. Measure change in local planning objections, council debate, community complaints and media attention over time.
3. Track whether new capacity announcements precede increases in affordability or fairness narratives.
4. Compare planned MW growth with grid and water infrastructure expansion.
5. Re-run the stress-test under mitigation scenarios before site expansion or policy approval.

**Key warning**

This model estimates **system pressure**, not probability of protest, violence or disorder. Social stability outcomes remain contingent on institutions, policy responses, community engagement and event-specific triggers.
""")
    now=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    st.markdown(f'<div class="footer">SOCIAL LOAD · AI Infrastructure Stability Monitor · {VERSION} · Principal Investigator: {PI} · Generated {now}</div>',unsafe_allow_html=True)
