"""Initial document, operational, and investigation persistence."""

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    for statement in [
        "CREATE EXTENSION IF NOT EXISTS vector",
        """CREATE TABLE documents (
            document_id text NOT NULL, version text NOT NULL, title text NOT NULL,
            service text NOT NULL, kind text NOT NULL, published_at timestamptz NOT NULL,
            content_hash text NOT NULL, content text NOT NULL,
            PRIMARY KEY(document_id, version))""",
        """CREATE TABLE chunks (
            chunk_id text NOT NULL, embedding_key text NOT NULL, document_id text NOT NULL,
            version text NOT NULL, section_id text NOT NULL, heading text NOT NULL,
            content text NOT NULL, start_line integer NOT NULL, end_line integer NOT NULL,
            embedding vector NOT NULL,
            search_vector tsvector GENERATED ALWAYS AS
              (to_tsvector('english', heading || ' ' || content)) STORED,
            PRIMARY KEY(chunk_id, embedding_key),
            FOREIGN KEY(document_id, version) REFERENCES documents(document_id, version))""",
        "CREATE INDEX chunks_text_idx ON chunks USING gin(search_vector)",
        "CREATE INDEX documents_scope_idx ON documents(service, published_at)",
        "CREATE TABLE services (service text PRIMARY KEY, dependencies jsonb NOT NULL)",
        """CREATE TABLE datasets (dataset_id text PRIMARY KEY, reference_time timestamptz NOT NULL,
            start_time timestamptz NOT NULL, description text NOT NULL)""",
        """CREATE TABLE log_events (
            event_id text PRIMARY KEY, dataset_id text NOT NULL REFERENCES datasets(dataset_id),
            service text NOT NULL, ts timestamptz NOT NULL, level text NOT NULL,
            code text NOT NULL, message text NOT NULL, available_at timestamptz NOT NULL)""",
        "CREATE INDEX logs_window_idx ON log_events(dataset_id,service,ts)",
        """CREATE TABLE metric_samples (
            sample_id text PRIMARY KEY, dataset_id text NOT NULL REFERENCES datasets(dataset_id),
            service text NOT NULL, ts timestamptz NOT NULL, metric text NOT NULL,
            value double precision NOT NULL, unit text NOT NULL, available_at timestamptz NOT NULL)""",
        "CREATE INDEX metrics_window_idx ON metric_samples(dataset_id,service,ts)",
        """CREATE TABLE change_events (
            change_id text PRIMARY KEY, dataset_id text NOT NULL REFERENCES datasets(dataset_id),
            service text NOT NULL, ts timestamptz NOT NULL, description text NOT NULL,
            version text NOT NULL, available_at timestamptz NOT NULL)""",
        """CREATE TABLE investigations (
            investigation_id text PRIMARY KEY, created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(), status text NOT NULL,
            request jsonb NOT NULL, report jsonb,
            CHECK(status IN ('running','completed','incomplete','failed')))""",
        """CREATE TABLE evidence_items (
            investigation_id text NOT NULL REFERENCES investigations(investigation_id),
            evidence_id text NOT NULL, payload jsonb NOT NULL,
            PRIMARY KEY(investigation_id,evidence_id))""",
        """CREATE TABLE tool_activity (
            investigation_id text NOT NULL REFERENCES investigations(investigation_id),
            ordinal integer NOT NULL, payload jsonb NOT NULL,
            PRIMARY KEY(investigation_id,ordinal))""",
    ]:
        op.execute(statement)


def downgrade():
    for table in [
        "tool_activity",
        "evidence_items",
        "investigations",
        "change_events",
        "metric_samples",
        "log_events",
        "datasets",
        "services",
        "chunks",
        "documents",
    ]:
        op.execute(f"DROP TABLE {table}")
