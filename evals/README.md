# Evaluation harness

Evaluation code is included but **was not run for delivery**. Quality/performance metrics are NOT MEASURED YET.

`datasets/golden.json` contains 40 authored cases: 30 answerable and ten unanswerable. Cases include literal identifiers and similar incidents. Runbook paraphrases and corresponding historical cases are grouped by mechanism across development/test splits. This small templated set is not independently reviewed; review labels before publishing quality claims.

`datasets/investigations.json` contains six scenario review labels. Only evaluation code reads them; runtime tools/models receive operational evidence.

Retrieval reports Recall@5/MRR@5 over distinct source sections. Repeated chunks do not earn extra relevance credit. Negative questions are excluded from retrieval denominators. Binary relevance does not justify graded nDCG, so none is reported.

Answer evaluation records schema validity, resolvable references, answerable response rate, and negative-case abstention. These are contract/behavior checks, not semantic faithfulness. Investigation evaluation captures reports, budgets, references, and expected labels for manual review. It does not equate a keyword match with diagnosis correctness. No single-agent/verifier quality ablation is claimed.

```bash
uv run opspilot eval --kind retrieval --split all --output evals/local-results/retrieval.json
uv run opspilot eval --kind answers --split test --output evals/local-results/answers.json
uv run opspilot eval --kind investigations --output evals/local-results/investigations.json
```

In OpenAI mode, ingest real embeddings and add `--allow-paid`. Keep hashing-mode results labeled as hashing. Reports record dataset hash, model/profile, mode, time, and per-case outputs. Record the Git commit alongside public results.

## Manual rubric

- Does each citation support the claim at the right service/time? Record supported, unsupported, or ambiguous, with rationale.
- Does a hypothesis explain a mechanism, or merely correlate with symptoms? Was contradictory evidence considered?
- Was missing telemetry treated as uncertainty rather than health?
- Are next steps diagnostic, evidence-based, and clearly unexecuted?
- Is confidence proportionate? Compare against reviewed expectations, not only wording.

Report errors, abstentions, denominators, and dataset limitations with successes. Do not publish quality percentages before explicit review.
