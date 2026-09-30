"""One real SDK adapter; the offline demo is explicitly a deterministic simulator."""

import asyncio
import json
from typing import Protocol

from openai import AsyncOpenAI
from pydantic import BaseModel, ValidationError

from opspilot.agents.prompts import PROMPTS


class ProviderFailure(RuntimeError):
    pass


class InvalidModelOutput(ValueError):
    pass


class StructuredModel(Protocol):
    usage: dict[str, int]

    async def generate(self, role: str, payload: dict, schema: type[BaseModel]) -> BaseModel: ...


class OpenAIModel:
    def __init__(self, settings):
        self.settings = settings
        self.usage = {"input_tokens": 0, "output_tokens": 0}

    async def generate(self, role, payload, schema):
        try:
            async with AsyncOpenAI(
                api_key=self.settings.openai_api_key.get_secret_value(),
                timeout=self.settings.provider_timeout_seconds,
                max_retries=0,
            ) as client:
                async with asyncio.timeout(self.settings.provider_timeout_seconds):
                    response = await client.responses.parse(
                        model=self.settings.llm_model,
                        input=[
                            {"role": "system", "content": PROMPTS[role]},
                            {"role": "user", "content": json.dumps(payload, default=str)},
                        ],
                        text_format=schema,
                        max_output_tokens=5000,
                        store=False,
                    )
            if response.usage:
                self.usage["input_tokens"] += response.usage.input_tokens
                self.usage["output_tokens"] += response.usage.output_tokens
            if response.output_parsed is None:
                raise InvalidModelOutput("Model refused or did not complete a structured response")
            return response.output_parsed
        except (InvalidModelOutput, ValidationError) as exc:
            raise InvalidModelOutput("Invalid structured model output") from exc
        except Exception as exc:
            raise ProviderFailure(f"Model provider unavailable ({type(exc).__name__})") from exc


def make_model(settings):
    if settings.mode == "demo":
        from opspilot.models.demo import DemoModel

        return DemoModel()
    return OpenAIModel(settings)
