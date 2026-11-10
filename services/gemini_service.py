"""All Gemini API calls live here. Every method returns ``None`` when Gemini is unavailable.

Gemini is only used for language tasks (parsing farm text, interpreting custom scenarios,
explaining results and summarising reports). It never computes or changes numbers.
Uses the official ``google-genai`` SDK: ``genai.Client(api_key=...).models.generate_content``.
"""
from __future__ import annotations

import json
import logging
import re

from config import GeminiSettings, get_gemini_settings

logger = logging.getLogger(__name__)
MAX_TEXT_CHARS = 8000
KEY_PATTERN = re.compile(r"\b(AIza[0-9A-Za-z_\-]{20,}|AQ\.[0-9A-Za-z_\-.]{20,})")

_NUMBER = {"type": "number"}
_STRINGS = {"type": "array", "items": {"type": "string"}}
FARM_SCHEMA = {
    "type": "object",
    "properties": {
        "farm_name": {"type": "string"}, "total_area_ha": _NUMBER, "n_plots": {"type": "integer"},
        "soil_type": {"type": "string"}, "soil_ph": _NUMBER, "soil_health_index": _NUMBER,
        "available_water_m3": _NUMBER, "budget_usd": _NUMBER, "seasons": _STRINGS,
        "rainfall_mm": {"type": "object", "properties": {s: _NUMBER for s in ("monsoon", "winter", "summer")}},
        "preferred_crops": _STRINGS, "excluded_crops": _STRINGS,
    },
}
SCENARIO_SCHEMA = {
    "type": "object",
    "properties": {
        "scenario_name": {"type": "string"}, "rainfall_multiplier": _NUMBER, "yield_stress_factor": _NUMBER,
        "input_cost_multiplier": _NUMBER, "market_price_multiplier": _NUMBER,
        "water_availability_multiplier": _NUMBER, "description": {"type": "string"},
    },
    "required": ["scenario_name"],
}
_TYPE_CHECKS = {
    "string": lambda v: isinstance(v, str),
    "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
    "integer": lambda v: (isinstance(v, int) and not isinstance(v, bool)) or (isinstance(v, float) and v.is_integer()),
    "array": lambda v: isinstance(v, list),
    "object": lambda v: isinstance(v, dict),
}


def redact_secrets(text: str, *secrets: str) -> str:
    """Remove the configured key and anything shaped like a Google API key."""
    for secret in secrets:
        if secret:
            text = text.replace(secret, "***")
    return KEY_PATTERN.sub("***", text)


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


def validate_json(data: dict, schema: dict) -> tuple[dict | None, list[str]]:
    """Keep only schema properties with the right JSON type.

    Returns ``(clean, problems)``; ``clean`` is ``None`` when a required key is missing or
    nothing usable remains. Range and vocabulary checks happen later in the agents.
    """
    problems: list[str] = []
    clean: dict = {}
    for key, value in data.items():
        spec = schema["properties"].get(key)
        if spec is None:
            problems.append(f"unexpected field '{key}'")
            continue
        if value is None:
            continue
        if not _TYPE_CHECKS[spec["type"]](value):
            problems.append(f"'{key}' should be {spec['type']}")
            continue
        if spec["type"] == "array":
            value = [v for v in value if _TYPE_CHECKS[spec["items"]["type"]](v)]
        elif spec["type"] == "object" and "properties" in spec:
            value, nested = validate_json(value, spec)
            problems += [f"{key}: {p}" for p in nested]
            if not value:
                continue
        clean[key] = value
    missing = [k for k in schema.get("required", []) if k not in clean]
    if missing:
        problems.append("missing required " + ", ".join(missing))
        return None, problems
    return (clean or None), problems


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

    def __repr__(self) -> str:
        return f"GeminiService(model={self.model!r}, available={self.available})"

    @property
    def available(self) -> bool:
        return self._client is not None or self.settings.configured

    @property
    def model(self) -> str:
        return self.settings.model

    def status(self) -> dict:
        """Safe-to-display status (never includes the key)."""
        return {"available": self.available, "model": self.model, "last_error": self.last_error}

    def _safe_error(self, exc: Exception) -> str:
        try:
            from google.genai import errors
        except ImportError:  # pragma: no cover - SDK is a hard dependency
            errors = None
        if errors is not None and isinstance(exc, errors.APIError):
            kind = {400: "invalid request", 401: "invalid API key", 403: "permission denied",
                    404: "model not found", 429: "rate limit or quota exceeded"}.get(
                exc.code, "server error" if isinstance(exc, errors.ServerError) else "API error")
            message = f"Gemini {kind} ({exc.code} {exc.status}): {exc.message}"
        else:
            message = f"{type(exc).__name__}: {exc}"
        return redact_secrets(message, self.settings.api_key)[:300]

    def _get_client(self):
        if self._client is None:
            from google import genai  # imported lazily so the app starts without touching the SDK
            self._client = genai.Client(api_key=self.settings.api_key)
        return self._client

    def generate_text(self, prompt: str, system_instruction: str | None = None, json_mode: bool = False,
                      temperature: float = 0.2, schema: dict | None = None) -> str | None:
        if not self.available:
            self.last_error = "Gemini API key not configured"
            return None
        try:
            from google.genai import types
            config = types.GenerateContentConfig(
                system_instruction=system_instruction,
                temperature=temperature,
                response_mime_type="application/json" if json_mode else None,
                response_json_schema=schema if json_mode else None,
            )
            response = self._get_client().models.generate_content(
                model=self.settings.model, contents=prompt, config=config)
            text = getattr(response, "text", None)
            self.last_error = None if text else "Gemini returned an empty response"
            return text
        except Exception as exc:  # network, auth, quota or SDK errors all fall back
            self.last_error = self._safe_error(exc)
            logger.warning("Gemini call failed: %s", self.last_error)
            return None

    def generate_json(self, prompt: str, system_instruction: str | None = None,
                      schema: dict | None = None) -> dict | None:
        """JSON object from Gemini, validated against ``schema`` when given; ``None`` if unusable."""
        text = self.generate_text(prompt, system_instruction, json_mode=True, temperature=0.0, schema=schema)
        if text is None:
            return None
        data = extract_json(text)
        if data is None:
            self.last_error = "Gemini response was not a JSON object"
            return None
        if schema is None:
            return data
        clean, problems = validate_json(data, schema)
        if problems:
            logger.info("Gemini JSON issues: %s", "; ".join(problems))
        if clean is None:
            self.last_error = "Gemini JSON failed validation: " + "; ".join(problems)[:200]
        return clean

    def parse_farm_description(self, text: str, crop_ids: list[str], soil_types: list[str]) -> dict | None:
        """Convert a natural-language farm description into a type-checked JSON dict."""
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
        return self.generate_json(prompt, system, FARM_SCHEMA)

    def interpret_scenario(self, text: str) -> dict | None:
        """Turn a described scenario into multipliers (range-checked by the scenario agent)."""
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
        return self.generate_json(prompt, system, SCENARIO_SCHEMA)

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
            "soil health), Risks, Performance under adverse scenarios, Assumptions and uncertainty. "
            "Keep it under 450 words.\n\nFACTS (JSON):\n" + json.dumps(facts, indent=1, default=str)[:12000]
        )
        return sanitize_text(self.generate_text(prompt, system, temperature=0.3))

    def summarize_report(self, report_markdown: str) -> str | None:
        system = ("Summarise the report in at most 5 bullet points. Use only numbers present in the "
                  "report. Mention that figures come from synthetic sample data.")
        return sanitize_text(self.generate_text(report_markdown[:12000], system), max_chars=2000)
