# ABI Frameworks Backend

This folder contains the ingestion and backend pipeline for the ABI Frameworks hackathon.

## What It Does

- Fetches patients from facilities `101`, `102`, and `103`
- Fans out per-patient jobs for diagnoses, coverage, notes, and assessments
- Handles `429` responses with `Retry-After` aware requeueing
- Stores raw route data in SQLite tables
- Marks patients ready when they have coverage and either notes or assessments
- Produces a `final_output` table with wound fields, Part B status, routing decision, and biller-friendly reason
- Exposes lightweight API endpoints for a dashboard or frontend teammate

## Setup

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Run Ingestion

```bash
python run_ingestion.py --workers 30 --db-path abi_pipeline.db
```

Useful environment variables:

| Variable | Default |
|---|---|
| `ABI_API_BASE_URL` | `https://hackathon.prod.pulsefoundry.ai` |
| `ABI_DB_PATH` | `./abi_pipeline.db` |
| `ABI_WORKERS` | `30` |
| `ABI_MAX_ATTEMPTS` | `8` |

## Run API

```bash
python run_api.py
```

Endpoints:

| Endpoint | Purpose |
|---|---|
| `GET /health` | Health check |
| `GET /summary` | Ingestion and routing counts |
| `GET /patients/ready` | Patients ready for extraction/classification |
| `GET /output` | Final biller-facing rows |
| `GET /output?decision=auto_accept` | Filter by routing decision |

## SQLite Tables

Raw ingestion:

- `patients`
- `diagnoses`
- `coverage`
- `notes`
- `assessments`

Pipeline state:

- `patient_status`
- `failed_jobs`

Dashboard handoff:

- `final_output`

## Routing Logic

- `auto_accept`: active Medicare Part B plus complete wound documentation
- `flag_for_review`: active Medicare Part B plus partial or ambiguous wound documentation
- `reject`: no active Medicare Part B, or no reliable wound data

Assessments are preferred over notes because they are structured. Notes are parsed with regexes for labeled SOAP/SPN notes and common shorthand such as `4.2x3.1x1.5cm`.
