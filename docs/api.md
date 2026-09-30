# API reference

Open `/docs` or `/openapi.json` on the running service for generated contracts.

| Endpoint | Behavior |
| --- | --- |
| `GET /health` | Process, release, active mode |
| `GET /ready` | Database/schema and matching index; no paid provider probe |
| `POST /query` | Knowledge answer, claims, passages, citations, model/profile |
| `POST /investigations` | Synchronous bounded execution, 201 persisted report |
| `GET /investigations/{uuid}` | Stored result, interrupted/running notice, or 404 |

Use timezone-aware timestamps. Operational windows must be positive, at most 24 hours, within fixture coverage, and no later than reference time. Datasets are `s01`–`s06`; services are checkout, payments, inventory, and postgres.

201 indicates record creation; inspect report status for diagnostic completion. Confidence is qualitative, not calibrated probability. Recommendations are unexecuted human diagnostic suggestions. Evidence includes source, service, observation/capture times, summary, and captured data. Empty telemetry can itself be meaningful missing evidence.

Invalid input returns 422, absent report IDs return 404, and unavailable dependencies can return 503. `X-Request-ID` correlates logs. There is no public authorization middleware in this local release.
