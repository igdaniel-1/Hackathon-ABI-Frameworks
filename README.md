# PulseAI — Wound Care Billing Pipeline

**ABI Frameworks Hackathon Submission**

An end-to-end data pipeline + interactive dashboard that ingests patient data from a mock PointClickCare (PCC) API, extracts wound details using GPT-5.4-mini, determines Medicare Part B billing eligibility, and presents actionable routing decisions to billers.

## Architecture

```
PCC Mock API ──▶ Ingestion Layer ──▶ Extraction Layer ──▶ Eligibility Engine ──▶ Dashboard
  (5 endpoints)    (retry on 429)     (GPT-5.4-mini)     (routing decisions)     (Neobrutalism UI)
```

### How It Works

1. **Ingest** — Fetches 300 patients across 3 facilities with diagnoses, coverage, notes, and assessments. Handles the 30% rate limit (429) with exponential backoff + jitter.
2. **Extract** — Pulls wound data from structured assessments (direct parse) and free-text clinical notes (GPT-5.4-mini). Handles all note formats: SOAP, prose, multi-wound, and Envive narrative.
3. **Route** — Checks Medicare Part B coverage, evaluates wound data completeness, assigns a routing decision (`auto_accept` / `flag_for_review` / `reject`) with a plain-English explanation.
4. **Display** — Neobrutalism-themed dashboard with stats, sortable/filterable patient table, patient detail modals, and a live AI pipeline log.

## Quick Start

```bash
# Install dependencies
npm install
pip install -r requirements.txt

# Set your OpenAI API key
export OPENAI_API_KEY="sk-..."        # macOS/Linux
$env:OPENAI_API_KEY="sk-..."          # PowerShell

# Run the frontend
npm start
# Opens http://localhost:3000

# Or run the pipeline standalone (CLI)
python -m pipeline
```

## Dashboard Features

- **Manual / Autonomous mode** — Run the pipeline on demand or let it start automatically
- **Live AI log** — Watch the pipeline process patients in real-time with colored log output
- **Phase progress** — Visual indicator showing Ingestion → Extraction → Complete
- **Stats bar** — At-a-glance counts: total patients, auto_accept, flag_for_review, reject
- **Sortable & filterable table** — Search by name/ID, filter by routing decision
- **Patient detail modal** — Click any patient to see wound info, measurements, coverage, ICD-10 codes, and the raw clinical note

## Routing Logic

| Decision | Criteria | Action |
|----------|----------|--------|
| **auto_accept** | Active MCB + wound type + complete measurements + drainage + clean format | Route to billing |
| **flag_for_review** | Active MCB + wound present, but data incomplete or ambiguous | Biller reviews manually |
| **reject** | No MCB coverage OR no wound data | Skip — not eligible |

Every decision includes a plain-English `reason` field:
> "Active Stage 2 pressure ulcer on sacrum with complete measurements (3.2 x 2.1 x 0.4 cm). Medicare Part B coverage is active. All required billing fields are documented."

## Project Structure

```
src/components/           React dashboard (Neobrutalism UI)
  Dashboard.js             Main layout + pipeline orchestration
  PatientTable.js           Sortable, filterable patient grid
  PatientDetail.js          Modal with full patient info
  StatsBar.js               Summary statistics cards
  AIPipelinePanel.js        AI interaction panel with live logs

pipeline/                  Python backend pipeline
  models.py                Data classes (Patient, WoundData, EligibilityResult)
  ingestion.py             PCC API client with retry logic
  extractor.py             GPT-5.4-mini wound data extraction
  eligibility.py           Routing engine with reason generation
  runner.py                Orchestrator (ingestion → extraction → eligibility → JSON)

api/                       Vercel serverless functions
  run_pipeline.py          GET /api/run_pipeline
  results.py               GET /api/results
```

## Technical Decisions

| Decision | Why |
|----------|-----|
| GPT-5.4-mini for extraction | Fast, cost-effective, handles all 4 clinical note formats with high accuracy |
| Assessments before notes | Structured data is always more reliable than free-text — only fall back to LLM when needed |
| Neobrutalism UI | Bold, distinctive, memorable for judges. High contrast = accessibility. |
| Frontend-driven pipeline | No server needed for demo — runs entirely in the browser + direct API calls |
| Parallel patient enrichment | 5 concurrent threads balance throughput against the 30% rate limit |

## Team

Built for the ABI Frameworks Hackathon.
