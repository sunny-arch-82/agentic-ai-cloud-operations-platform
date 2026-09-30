import asyncio

from opspilot.models.llm import InvalidModelOutput, make_model
from opspilot.rag.retrieval import Retriever
from opspilot.schemas.contracts import Answer, AnswerDraft


async def answer_query(db, settings, request, model=None):
    async with asyncio.timeout(settings.deadline_seconds):
        retriever = Retriever(db, settings)
        rows = await retriever.search(
            request.question, request.service, request.reference_time, request.retrieval_mode
        )
        evidence = retriever.evidence(rows, settings.context_chars)
        if not evidence:
            result = AnswerDraft(
                status="insufficient_evidence",
                answer="No applicable knowledge was retrieved.",
                claims=[],
            )
        else:
            provider = model or make_model(settings)
            result = await provider.generate(
                "answer",
                {
                    "question": request.question,
                    "evidence": [e.model_dump(mode="json") for e in evidence],
                },
                AnswerDraft,
            )
            result = AnswerDraft.model_validate(
                result.model_dump() if hasattr(result, "model_dump") else result
            )
        available = {e.evidence_id for e in evidence}
        if any(not c.evidence_ids or not set(c.evidence_ids) <= available for c in result.claims):
            raise InvalidModelOutput("Answer contained missing or invalid citations")
        if result.status == "answered" and not result.claims:
            raise InvalidModelOutput("Answered response had no supported claims")
        if result.status == "insufficient_evidence":
            result = AnswerDraft(
                status=result.status,
                answer="The available knowledge does not support an answer to this question.",
                claims=[],
            )
        else:
            result.answer = "\n\n".join(c.statement for c in result.claims)
        return Answer(
            **result.model_dump(),
            evidence=evidence,
            citations=sorted({i for c in result.claims for i in c.evidence_ids}),
            mode=settings.mode,
            model=settings.model_id,
            embedding_key=settings.embedding_key,
        )
