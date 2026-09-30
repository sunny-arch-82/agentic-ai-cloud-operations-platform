# Licensing and provenance

The root MIT license covers original OpsPilot code, documentation, and original synthetic fixtures. It does not relicense packages, images, services, or model assets.

Python versions/download hashes are locked in `uv.lock`. Installed distribution-declared licensing metadata is recorded in `third-party-metadata.json`. This metadata inventory is not a legal audit; verify missing/ambiguous information against upstream releases before redistributing built environments.

Pay attention to psycopg/psycopg-binary and bundled native libraries when distributing containers. Python, PostgreSQL, pgvector, uv, base-image packages, and Actions retain upstream terms/notices. This ZIP does not vendor `.venv`, model weights, or a database image.

Upstream projects:

- https://github.com/fastapi/fastapi
- https://github.com/pydantic/pydantic
- https://github.com/langchain-ai/langgraph
- https://github.com/modelcontextprotocol/python-sdk
- https://github.com/sqlalchemy/sqlalchemy
- https://github.com/psycopg/psycopg
- https://github.com/pgvector/pgvector
- https://github.com/sqlalchemy/alembic
- https://github.com/openai/openai-python
- https://github.com/astral-sh/uv

OpenAI services require the user's account/key and current provider terms; MIT grants no model-service rights. No model weights, cloud credentials, or proprietary operational data are included. All fixture narratives and values are fictional and should remain labeled synthetic.
