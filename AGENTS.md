# AGENTS.md

This file provides guidance to WARP (warp.dev) when working with code in this repository.

## Current repo reality checks
- Main runnable app entrypoint in this checkout is `App.py`.
- `README.md` references `App_refined.py` and `resume_classifier.py`, but those files are not present in this repository snapshot.
- There is no committed automated test suite (`tests/` not present) and no configured linter config file.

## Common development commands
## Environment setup
- Create and activate a virtual environment:
  - PowerShell:
    - `python -m venv .venv`
    - `.venv\Scripts\Activate.ps1`
  - bash:
    - `python -m venv .venv`
    - `source .venv/bin/activate`
- Install dependencies:
  - `pip install -r requirements.txt`
- Install required spaCy model:
  - `python -m spacy download en_core_web_sm`

## Run the app
- Start Streamlit locally:
  - `streamlit run App.py --server.port 8502`

## Optional integrations used by the app
- Initialize MySQL schema (only if using MySQL mode):
  - `mysql -u root -p < setup_database.sql`
- Local Ollama chatbot setup:
  - `ollama serve`
  - `ollama pull phi`
- Environment bootstrap:
  - `Copy-Item .env.example .env` (PowerShell)
  - `cp .env.example .env` (bash)

## Validation commands used during development
- Syntax check the codebase:
  - `python -m compileall .`
- If adding pytest tests, run all tests:
  - `python -m pytest`
- If adding pytest tests, run a single test:
  - `python -m pytest tests/test_resume_parser.py::test_extract_skills`

## Architecture overview (big picture)
## App orchestration layer
- `App.py` is the central orchestrator: it initializes config/theme/session state, handles resume upload, calls parsing/scoring/recommendation/chat services, and renders both user and admin paths.
- Streamlit secrets are hydrated into environment variables early in `App.py` before config/database initialization.

## Core request/data flow
1. User uploads PDF in `App.py`.
2. `ResumeParser` (`resume_parser.py`) extracts:
   - contact info (email/phone/links),
   - candidate name heuristically,
   - skills via spaCy `PhraseMatcher` + fuzzy matching.
3. `AnalyticsUtils` (`utils.py`) computes resume score breakdown (basic info, skills, sections, achievements, recency, links) and improvement suggestions.
4. Job recommendations are merged in `App.py` from:
   - Jooble API (`api_services.py`),
   - scraper sources (`job_scrapers.py`: Internshala, GitHub search, RemoteOK),
   then normalized and deduplicated by URL.
5. Course recommendations come from static catalogs in `Courses.py`, selected based on extracted skills.
6. Chat assistant uses Ollama via `chat_service.py`, optionally injecting a resume-derived context.
7. If DB is available, user interaction summary is persisted via `DatabaseManager.insert_user_data` (`database.py`).

## Configuration and persistence boundaries
- `config.py` loads `.env` and determines DB mode (`sqlite` fallback when MySQL credentials are absent).
- `database.py` supports both SQLite and MySQL, can update `.env` from UI credential changes, and initializes `user_data` table automatically.
- The app is designed to keep running even if DB/API/Ollama integrations are unavailable; features degrade rather than hard-fail.

## UI and styling boundaries
- `styles.py` contains centralized CSS/theme helpers used heavily by `App.py`.
- `ui.py` has extra UI helper/footer functions; current main flow relies mostly on inline markup plus `StyleManager`.

## High-value files to read first when making changes
- `App.py` (entrypoint + integration wiring)
- `resume_parser.py` (extraction quality and parsing behavior)
- `utils.py` (`AnalyticsUtils` scoring and resume suggestions)
- `job_scrapers.py` and `api_services.py` (recommendation inputs)
- `chat_service.py` (Ollama behavior and prompt shaping)
- `database.py` + `config.py` (runtime mode, persistence, env handling)
