.PHONY: dev test lint fmt

dev:
	uvicorn src.triage_agent.main:app --reload --port 8000

test:
	pytest

lint:
	ruff check .

fmt:
	ruff format .
