# The Absence Signal — Flagship Intelligence Workbench V3

**Principal Investigator:** Mohd Khairul Ridhuan bin Mohd Fadzil

## What this project answers
1. Who is the company?
2. What does it do?
3. Which industries does it connect to?
4. Does it have an overseas / multi-jurisdiction network?
5. Does observable reality support its claimed profile?
6. What has changed recently?
7. Does the network make sense for the business model?
8. What does not fit?
9. So what?
10. What should an investigator verify next?

## Core analytical layers
- Company Intelligence Snapshot
- Multi-source Entity Resolution
- Industry Ecosystem
- Overseas Network
- Expected Footprint Divergence
- Network Coherence
- Corporate Behavioural Drift
- Evidence Confidence
- Evidence Ledger
- Falsification Requirement
- Executive Analyst Brief

## Live / optional data
- GLEIF: live, no key required
- OFAC SDN names: current public feed
- Companies House: optional API key
- OpenCorporates: optional API token

## Run
```bash
pip install -r requirements.txt
streamlit run streamlit_app.py
```

## Optional secrets
Create `.streamlit/secrets.toml` locally or configure Streamlit Cloud Secrets:
```toml
COMPANIES_HOUSE_API_KEY = "your_key"
OPENCORPORATES_API_TOKEN = "your_token"
```

## Important
This is an intelligence triage framework, not a fraud detector. Public-source absence, name similarity, or network proximity must never be treated as proof of wrongdoing.
