"""Deterministic reference validation; semantic truth still needs evaluation."""

from opspilot.schemas.contracts import Draft


def validate_draft(draft: Draft, evidence_ids: set[str]):
    issues = []

    def valid(claim, require_citation=True):
        refs = claim.evidence_ids + getattr(claim, "contradictory_evidence_ids", [])
        if (require_citation and not claim.evidence_ids) or any(
            r not in evidence_ids for r in refs
        ):
            issues.append(f"Removed claim with missing or invalid citations: {claim.statement}")
            return False
        return True

    return Draft(
        observations=[c for c in draft.observations if valid(c)],
        hypotheses=[c for c in draft.hypotheses if valid(c)],
        missing_evidence=draft.missing_evidence,
        recommended_next_steps=[c for c in draft.recommended_next_steps if valid(c, False)],
    ), issues


def all_citations(draft: Draft):
    refs = set()
    for claim in [*draft.observations, *draft.hypotheses, *draft.recommended_next_steps]:
        refs.update(claim.evidence_ids)
        refs.update(getattr(claim, "contradictory_evidence_ids", []))
    return sorted(refs)
