"""Optional Google Gemini client for research narratives.

Works only when ``GEMINI_API_KEY`` is set; otherwise ``available`` is False and
``generate`` returns None so callers fall back to rule-based text.
"""
from __future__ import annotations

import json
import logging

from config import Settings, get_settings

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "You are an agronomist and farm economist. Using only the JSON results provided, write a "
    "concise research report in Markdown for a smallholder farmer with sections: Summary, "
    "Why this plan, Risks, and Recommendations. Quote numbers from the data; do not invent data."
)


class GeminiService:
    def __init__(self, settings: Settings | None = None, client=None):
        self.settings = settings or get_settings()
        self._client = client
        self.last_error: str | None = None

    @property
    def model(self) -> str:
        return self.settings.gemini_model

    @property
    def available(self) -> bool:
        return self._client is not None or bool(self.settings.gemini_api_key)

    def _get_client(self):
        if self._client is None:
            from google import genai

            self._client = genai.Client(api_key=self.settings.gemini_api_key)
        return self._client

    @staticmethod
    def build_prompt(summary: dict) -> str:
        return f"{SYSTEM_PROMPT}\n\nResults:\n```json\n{json.dumps(summary, indent=2, default=str)}\n```"

    def generate(self, prompt: str) -> str | None:
        """Model text for ``prompt``, or None if Gemini is unavailable or the call fails."""
        self.last_error = None
        if not self.available:
            return None
        try:
            response = self._get_client().models.generate_content(model=self.model, contents=prompt)
        except Exception as exc:  # network, auth or quota errors must not break the app
            self.last_error = f"{type(exc).__name__}: {exc}"
            logger.warning("Gemini request failed: %s", self.last_error)
            return None
        text = (getattr(response, "text", None) or "").strip()
        return text or None

    def research_narrative(self, summary: dict) -> str | None:
        return self.generate(self.build_prompt(summary))
