.PHONY: dev-local dev test stop

dev-local:
	cd backend && uvicorn src.triage_agent.main:app --reload --port 8000 &
	cd frontend && pnpm dev

dev:
	docker-compose up --build

test:
	cd backend && pytest

stop:
	docker-compose down
