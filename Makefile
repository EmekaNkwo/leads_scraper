PYTHON := venv/Scripts/python.exe

.PHONY: install run api test dev

install:
	"$(PYTHON)" -m pip install -r backend/requirements.txt
	"$(PYTHON)" -m playwright install chromium
	cd frontend && pnpm install

run:
	cd backend && "../$(PYTHON)" scraper.py

api:
	cd backend && "../$(PYTHON)" -m uvicorn api:app --host 127.0.0.1 --port 8000

dev:
	cd frontend && pnpm dev

test:
	cd backend && "../$(PYTHON)" -m pytest -q
