.PHONY: setup db bootstrap run lint test integration eval mcp demo
setup:
	uv sync --frozen
db:
	docker compose up -d db
bootstrap:
	uv run opspilot bootstrap
run:
	uv run uvicorn opspilot.api.app:create_app --factory --host 127.0.0.1 --port 8000
lint:
	uv run ruff check .
	uv run ruff format --check .
test:
	uv run pytest -m 'not integration'
integration:
	uv run pytest -m integration
eval:
	uv run opspilot eval --kind retrieval --output evals/local-results/retrieval.json
mcp:
	uv run opspilot mcp-check
demo:
	uv run opspilot demo --scenario s01
