import random
import time

from google import genai
from google.genai import errors, types
from pydantic import ValidationError

from .prompts import SYSTEM_PROMPT
from .schema import SCHEMA_VERSION, ResumeExtraction

_RETRYABLE = {429, 500, 502, 503, 504}


class ExtractionError(Exception):
    pass


def _thinking(model: str, level: str) -> types.ThinkingConfig | None:
    # Thinking tokens are billed as output and extraction needs none.
    if level:  # Gemini 3.x: lowest level the model supports (see GEMINI_THINKING_LEVEL)
        return types.ThinkingConfig(thinking_level=level)
    if "2.5" in model:
        return types.ThinkingConfig(thinking_budget=0)
    return None


class GeminiExtractor:
    """Callable: text -> (resume_dict, meta_dict). Synchronous on purpose."""

    def __init__(
        self, api_key: str, model: str, max_output_tokens: int = 2048, retries: int = 3,
        thinking_level: str = "", servce_tier: str | None = "flex"
    ):
        self._client = genai.Client(api_key=api_key)
        self._model, self._retries = model, retries
        self._config = types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            response_mime_type="application/json",
            response_schema=ResumeExtraction,
            temperature=0.0,
            max_output_tokens=max_output_tokens,
            thinking_config=_thinking(model, thinking_level),
            service_tier=servce_tier, 
        )   

    def __call__(self, text: str) -> tuple[dict, dict]:
        resp = self._generate(text)

        data = resp.parsed
        if not isinstance(data, ResumeExtraction):
            try:
                data = ResumeExtraction.model_validate_json(resp.text or "")
            except ValidationError as e:  # usually: output cut off by max_output_tokens
                raise ExtractionError("model output failed schema validation") from e

        u = resp.usage_metadata
        meta = {
            "model": self._model,
            "schema_version": SCHEMA_VERSION,
            "input_tokens": (u.prompt_token_count or 0) if u else 0,
            "output_tokens": ((u.candidates_token_count or 0) + (u.thoughts_token_count or 0)) if u else 0,
        }
        return data.model_dump(), meta

    def _generate(self, text: str):
        for attempt in range(self._retries + 1):
            try:
                return self._client.models.generate_content(
                    model=self._model, contents=text, config=self._config
                )
            except errors.APIError as e:
                if e.code not in _RETRYABLE or attempt == self._retries:
                    raise ExtractionError(f"gemini error {e.code}") from e
                time.sleep(min(2**attempt, 8) + random.random())  # backoff + jitter
        raise AssertionError("unreachable")
