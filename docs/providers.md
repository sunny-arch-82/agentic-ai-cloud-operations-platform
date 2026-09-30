# Provider behavior

Demo mode uses normalized lexical hashing and deterministic rules over captured evidence. It exercises integration and contracts, not neural embeddings, LLM reasoning, or general diagnostic accuracy. It never reads evaluation labels. Preserve its mode labels when demonstrating it.

OpenAI mode uses the official SDK, Responses API Pydantic parsing, and embedding endpoint. Defaults are `gpt-4.1-mini` and `text-embedding-3-small` at 512 dimensions. SDK retries are disabled; investigation schema-repair retries are bounded separately. Requests use `store=False` and a bounded output-token limit. Only environment configuration supplies credentials.

Tools are selected through structured action decisions and dispatched by application code over MCP. The model does not execute shell or SQL. Refusals, missing parsed output, malformed data, and provider failures do not become successful answers. Embedding count/dimension/finite-value checks precede storage.

Official references consulted:

- https://developers.openai.com/api/docs/guides/structured-outputs
- https://developers.openai.com/api/docs/guides/embeddings
- https://developers.openai.com/api/docs/models/gpt-4.1-mini

No paid API calls were executed for delivery. Confirm account/model compatibility and evaluate with your configuration. A new embedding profile requires ingestion. Per-request limits do not enforce monthly spend.
