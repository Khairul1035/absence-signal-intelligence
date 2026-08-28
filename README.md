# The Absence Signal — Intelligence Workbench 

Principal Investigator: Mohd Khairul Ridhuan bin Mohd Fadzil

## What V2 adds
- Multi-source entity resolution
- GLEIF live entity layer
- OFAC SDN name-similarity cue
- Optional Companies House connector
- Optional OpenCorporates connector
- Expected Footprint Divergence scoring
- Evidence confidence
- Evidence ledger / provenance
- Chronology
- Network collection questions
- Analyst brief
- Falsification discipline

## Run
```bash
pip install -r requirements.txt
streamlit run streamlit_app.py
```

## Optional API keys
Create `.streamlit/secrets.toml` locally or use Streamlit Cloud Secrets:
```toml
COMPANIES_HOUSE_API_KEY = "..."
OPENCORPORATES_API_TOKEN = "..."
```

The app runs without these keys; they simply improve entity coverage.

## Important analytic caveat
The framework is a triage and collection-prioritisation system. It does not establish wrongdoing.
