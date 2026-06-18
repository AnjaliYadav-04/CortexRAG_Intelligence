.PHONY: help install dev docker-up docker-down seed eval test lint clean

help:
	@echo ""
	@echo "Enterprise Advanced RAG — Makefile"
	@echo "====================================="
	@echo "  make install     Install Python dependencies"
	@echo "  make dev         Start FastAPI in dev mode"
	@echo "  make ui          Start Streamlit UI"
	@echo "  make docker-up   Start all infra (Qdrant, Postgres, Redis)"
	@echo "  make docker-down Stop infra"
	@echo "  make seed        Seed K8s docs into Qdrant"
	@echo "  make eval        Run Ragas evaluation suite"
	@echo "  make test        Run unit tests"
	@echo "  make lint        Run ruff linter"
	@echo "  make clean       Remove __pycache__ and .pyc files"
	@echo ""

install:
	pip install -r requirements.txt

dev:
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

ui:
	streamlit run app/ui/streamlit_app.py --server.port 8501

docker-up:
	docker-compose up -d qdrant postgres redis
	@echo "Waiting for services..."
	@sleep 5
	@echo "Infrastructure ready ✅"

docker-down:
	docker-compose down

seed:
	python scripts/seed_data.py --source local

eval:
	python scripts/run_evals.py --questions 5

test:
	pytest tests/ -v

lint:
	ruff check app/ tests/

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete
