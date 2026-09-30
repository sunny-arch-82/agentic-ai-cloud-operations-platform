import json

from sqlalchemy import text


def seed_operational(db, data_dir):
    data = json.loads((data_dir / "operations.json").read_text())
    with db.engine.begin() as conn:
        for service, dependencies in data["services"].items():
            conn.execute(
                text(
                    "INSERT INTO services VALUES (:service,CAST(:deps AS jsonb)) ON CONFLICT DO NOTHING"
                ),
                {"service": service, "deps": json.dumps(dependencies)},
            )
        specs = [
            ("datasets", "datasets", ["dataset_id", "reference_time", "start_time", "description"]),
            (
                "logs",
                "log_events",
                [
                    "event_id",
                    "dataset_id",
                    "service",
                    "ts",
                    "level",
                    "code",
                    "message",
                    "available_at",
                ],
            ),
            (
                "metrics",
                "metric_samples",
                [
                    "sample_id",
                    "dataset_id",
                    "service",
                    "ts",
                    "metric",
                    "value",
                    "unit",
                    "available_at",
                ],
            ),
            (
                "changes",
                "change_events",
                [
                    "change_id",
                    "dataset_id",
                    "service",
                    "ts",
                    "description",
                    "version",
                    "available_at",
                ],
            ),
        ]
        for key, table, columns in specs:
            # Identifiers are code-owned constants; every value is bound.
            if data[key]:
                conn.execute(
                    text(
                        f"INSERT INTO {table} ({','.join(columns)}) VALUES "
                        f"({','.join(':' + c for c in columns)}) ON CONFLICT DO NOTHING"
                    ),
                    data[key],
                )
    return {key: len(data[key]) for key in ["datasets", "logs", "metrics", "changes"]}
