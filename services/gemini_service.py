"""All Gemini API calls live here. Every method returns ``None`` when Gemini is unavailable.

Gemini is only used for language tasks (parsing farm text, interpreting custom scenarios,
explaining results and summarising reports). It never computes or changes numbers.
"""
from __future__ import annotations

import json
import logging
import re

from config import GeminiSettings, get_gemini_settings

logger = logging.getLogger(__name__)
MAX_TEXT_CHARS = 8000


def extract_json(text: str | None) -> dict | None:
    """Parse a JSON object from model output, tolerating code fences and surrounding prose."""
    if not text:
        return None
    cleaned = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.MULTILINE).strip()
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
        if not match:
            return None
        try:
            data = json.loads(match.group(0))
        except json.JSONDecodeError:
            return None
    return data if isinstance(data, dict) else None


def sanitize_text(text: str | None, max_chars: int = MAX_TEXT_CHARS) -> str | None:
    """Strip code fences, HTML tags and control characters; cap the length."""
    if not text:
        return None
    text = re.sub(r"```[a-zA-Z]*", "", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = "".join(ch for ch in text if ch.isprintable() or ch in "\n\t")
    text = text.strip()
    return text[:max_chars] if text else None


class GeminiService:
    """Thin wrapper around the official ``google-genai`` client with graceful fallback."""

    def __init__(self, settings: GeminiSettings | None = None, client=None):
        self.settings = settings or get_gemini_settings()
        self._client = client
        self.last_error: str | None = None

    @property
    def available(self) -> bool:
        return self._client is not None or self.settings.configured

    @property
    def model(self) -> str:
        return self.settings.model

    def _safe_error(self, exc: Exception) -> str:
        message = f"{type(exc).__name__}: {exc}"
        if self.settings.api_key:
            message = message.replace(self.settings.api_key, "***")
        return message[:300]

    def _get_client(self):
        if self._client is None:
            from google import genai  # imported lazily so the app runs without the SDK configured
            self._client = genai.Client(api_key=self.settings.api_key)
        return self._client

    def generate_text(self, prompt: str, system_instruction: str | None = None,
                      json_mode: bool = False, temperature: float = 0.2) -> str | None:
        if not self.available:
            self.last_error = "Gemini API key not configured"
            return None
        try:
            from google.genai import types
            config = types.GenerateContentConfig(
                system_instruction=system_instruction,
                temperature=temperature,
                response_mime_type="application/json" if json_mode else None,
            )
            response = self._get_client().models.generate_content(
                model=self.settings.model, contents=prompt, config=config)
            self.last_error = None
            return getattr(response, "text", None)
        except Exception as exc:  # network, auth, quota or SDK errors all fall back
            self.last_error = self._safe_error(exc)
            logger.warning("Gemini call failed: %s", self.last_error)
            return None

    def generate_json(self, prompt: str, system_instruction: str | None = None) -> dict | None:
        return extract_json(self.generate_text(prompt, system_instruction, json_mode=True, temperature=0.0))

    def parse_farm_description(self, text: str, crop_ids: list[str], soil_types: list[str]) -> dict | None:
        """Convert a natural-language farm description into a raw JSON dict (unvalidated)."""
        system = (
            "You extract structured farm data. Reply with one JSON object only. Use only facts "
            "stated in the text; omit a field (do not guess) when it is not stated. Convert acres "
            "to hectares (1 acre = 0.404686 ha)."
        )
        prompt = (
            "Fields: farm_name (string), total_area_ha (number), n_plots (integer), soil_type "
            f"(one of {soil_types}), soil_ph (number), soil_health_index (0-100), "
            "available_water_m3 (number), budget_usd (number), seasons (list of monsoon/winter/summer), "
            "rainfall_mm (object season -> mm), preferred_crops and excluded_crops (lists of "
            f"{crop_ids}).\n\nFarm description:\n{text[:3000]}"
        )
        return self.generate_json(prompt, system)

    def interpret_scenario(self, text: str) -> dict | None:
        """Turn a described scenario into multipliers (validated by the scenario agent)."""
        system = (
            "You translate a farming risk scenario into numeric multipliers relative to normal "
            "conditions (1.0 = unchanged). Reply with one JSON object only."
        )
        prompt = (
            "Keys: scenario_name (short string), rainfall_multiplier (0-3), yield_stress_factor "
            "(0.3-1.2), input_cost_multiplier (0.5-3), market_price_multiplier (0.3-2), "
            "water_availability_multiplier (0-2), description (one sentence).\n\n"
            f"Scenario:\n{text[:1500]}"
        )
        return self.generate_json(prompt, system)

    def explain_strategy(self, facts: dict) -> str | None:
        """Explain an optimised strategy using only the supplied numbers."""
        system = (
            "You are an agricultural strategy analyst. Explain the optimisation results for a "
            "farmer in clear Markdown. Use ONLY numbers that appear in the provided JSON facts; "
            "never invent, estimate or recompute figures. The data is synthetic sample data, so "
            "say so and do not present it as verified agronomic advice."
        )
        prompt = (
            "Write sections: Summary, Why this crop allocation, Trade-offs (profit, yield, water, "
            "soil health), Performance under adverse scenarios, Assumptions and uncertainty. "
            "Keep it under 450 words.\n\nFACTS (JSON):\n" + json.dumps(facts, indent=1, default=str)[:12000]
        )
        return sanitize_text(self.generate_text(prompt, system, temperature=0.3))

    def summarize_report(self, report_markdown: str) -> str | None:
        system = ("Summarise the report in at most 5 bullet points. Use only numbers present in the "
                  "report. Mention that figures come from synthetic sample data.")
        return sanitize_text(self.generate_text(report_markdown[:12000], system), max_chars=2000)
