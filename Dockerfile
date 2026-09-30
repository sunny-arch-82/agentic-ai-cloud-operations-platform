FROM python:3.12-slim
WORKDIR /app
RUN pip install --no-cache-dir uv==0.12.18
COPY pyproject.toml uv.lock README.md /app/
COPY src /app/src
RUN uv sync --frozen --no-dev --no-editable
COPY migrations /app/migrations
COPY alembic.ini /app/
COPY data /app/data
COPY evals /app/evals
RUN useradd --create-home --uid 10001 opspilot && chown -R opspilot:opspilot /app
USER opspilot
ENV PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1
EXPOSE 8000
CMD ["uvicorn", "opspilot.api.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
