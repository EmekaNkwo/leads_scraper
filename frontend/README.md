# Frontend

This is the Next.js dashboard for the `leads_scraper` app. It provides the UI for:

- starting scrape jobs
- tracking live job progress
- resuming from checkpoints
- cancelling running jobs
- reviewing job history
- downloading completed CSV exports

The frontend talks to the FastAPI backend and is not meant to run by itself without the scraper API.

## Prerequisites

- Node.js 20.9+
- `pnpm`
- the backend API running locally or reachable over HTTP

Install `pnpm` if needed:

```bash
npm install -g pnpm
```

## Install

From the `frontend/` directory:

```bash
pnpm install
```

Or from the repo root:

```bash
./run.sh install
```

On Windows:

```bat
run.bat install
```

## Development

Start the frontend dev server:

```bash
pnpm dev
```

Open `http://localhost:3000`.

## Backend Connection

The frontend rewrites `/api/*` requests to the backend defined by `BACKEND_URL`.

Default backend:

```text
http://127.0.0.1:8000
```

This comes from `next.config.ts`.

If your backend is running somewhere else, set `BACKEND_URL` before starting the frontend from the `frontend/` directory.

macOS / Linux:

```bash
BACKEND_URL=http://127.0.0.1:8000 pnpm dev
```

Windows Command Prompt:

```bat
set BACKEND_URL=http://127.0.0.1:8000 && pnpm dev
```

Windows PowerShell:

```powershell
$env:BACKEND_URL="http://127.0.0.1:8000"
pnpm dev
```

## Typical Local Workflow

From the repo root:

macOS / Linux:

```bash
./run.sh stack
```

Windows, using two terminals:

```bat
run.bat api
run.bat dev
```

That gives you:

- frontend at `http://localhost:3000`
- backend docs at `http://127.0.0.1:8000/docs`

## Available Scripts

- `pnpm dev`: start the Next.js development server
- `pnpm build`: create a production build
- `pnpm start`: run the production server
- `pnpm lint`: run ESLint

## Notes

- The frontend expects the backend job API to be available.
- Active and recent jobs come from the backend's in-memory job store, so a backend restart clears existing job IDs.
- For full project setup, backend install steps, and deployment notes, see the repo root `README.md`.
