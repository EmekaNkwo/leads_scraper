# Leads Scraper

Google Maps leads scraper with enrichment, export pipeline, REST API, and React frontend.

## Features

- Scrapes leads from Google Maps search queries.
- Supports multiple queries in one run.
- Optional website enrichment for email/owner/team hints.
- Exports per-query CSV and JSON files.
- Appends all runs to a master CSV.
- Supports checkpoints/resume and run logs.
- Auto-timeout: scales with requested results, capped at 30 min.
- REST API with Swagger docs.
- React frontend (Next.js + shadcn/ui + Redux Toolkit).

## Project Structure

```
leads_scraper/
├── backend/
│   ├── api.py                  # FastAPI REST API
│   ├── scraper.py              # CLI entrypoint
│   ├── scraper_maps.py         # Google Maps scraping logic
│   ├── scraper_enrichment.py   # Website enrichment pass
│   ├── scraper_exporters.py    # CSV/JSON export helpers
│   ├── scraper_utils.py        # Logging, confidence, checkpoints
│   ├── scraper_models.py       # Lead data model
│   ├── scraper_config.py       # Config loader
│   ├── scraper_config.json     # Default runtime config
│   ├── requirements.txt        # Python dependencies
│   └── tests/                  # pytest tests
├── frontend/                   # Next.js + shadcn/ui + Redux Toolkit
│   ├── src/
│   │   ├── app/                # Pages and layout
│   │   ├── components/         # UI components
│   │   ├── hooks/              # Business logic hooks
│   │   ├── lib/                # Redux store + RTK Query API
│   │   └── types/              # TypeScript types
│   └── package.json
├── Makefile                    # Unix shortcuts
├── run.bat                     # Windows shortcuts
└── README.md
```

## Requirements

- Python 3.10+
- Node.js 18+
- Chromium for Playwright

## Quick Start

Install everything:

```bash
# With Makefile (Unix)
make install

# With run.bat (Windows)
run.bat install
```

Or manually:

```bash
pip install -r backend/requirements.txt
python -m playwright install chromium
cd frontend && pnpm install
```

## Running

### CLI scraper

```bash
cd backend
python scraper.py
python scraper.py --queries "electronics store lagos" --max-results 50
python scraper.py --show-browser
python scraper.py --resume
```

### API server

```bash
cd backend
python api.py
```

Or: `make api` / `run.bat api`

- Swagger UI: http://127.0.0.1:8000/docs
- ReDoc: http://127.0.0.1:8000/redoc

### Frontend

```bash
cd frontend
pnpm dev
```

Or: `make dev` / `run.bat dev`

Opens at http://localhost:3000 (proxies API calls to :8000).

## CLI Options

```
--config            Path to JSON config (default: scraper_config.json)
--queries           Override query list
--max-results       Max leads per query
--max-scrolls       Max scroll iterations per query
--max-runtime-seconds  Per-query time cap (0 = auto)
--output-dir        Output folder override
--show-browser      Disable headless mode
--no-enrich         Skip website enrichment
--no-json           Skip JSON export
--resume            Resume from checkpoint
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Server health check with uptime |
| `GET` | `/config` | Current default configuration |
| `POST` | `/scrape` | Submit a new scraping job (async) |
| `GET` | `/scrape` | List all jobs (filter by status) |
| `GET` | `/scrape/{job_id}` | Poll job status and results |
| `GET` | `/scrape/{job_id}/csv` | Download job leads as CSV |
| `GET` | `/exports` | List recent export files |
| `GET` | `/exports/{filename}` | Download a specific export file |

## Output

Generated inside `backend/`:

- `csv_exports/leads_<query>_<timestamp>.csv`
- `csv_exports/leads_<query>_<timestamp>.json`
- `csv_exports/master_leads.csv`
- `logs/run_<run_id>.log`
- `checkpoints/<query>.json`

## Tests

```bash
make test
# or
cd backend && python -m pytest -q
```
