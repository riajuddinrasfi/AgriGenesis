from types import SimpleNamespace

from agents.research_agent import ResearchAgent
from config import Settings
from services.gemini_service import GeminiService


class FakeModels:
    def __init__(self, text=None, error=None):
        self.text, self.error, self.calls = text, error, []

    def generate_content(self, model, contents):
        self.calls.append((model, contents))
        if self.error:
            raise self.error
        return SimpleNamespace(text=self.text)


def fake_client(**kwargs):
    return SimpleNamespace(models=FakeModels(**kwargs))


def test_unavailable_without_key():
    service = GeminiService(Settings(gemini_api_key=""))
    assert not service.available and service.generate("hi") is None


def test_generate_uses_configured_model():
    client = fake_client(text="  ## Summary\nGrow lentils.  ")
    service = GeminiService(Settings(gemini_model="gemini-test"), client=client)
    assert service.generate("prompt") == "## Summary\nGrow lentils."
    assert client.models.calls == [("gemini-test", "prompt")]


def test_errors_and_empty_responses_fall_back():
    failing = GeminiService(Settings(gemini_api_key="x"), client=fake_client(error=RuntimeError("quota")))
    assert failing.generate("p") is None and "quota" in failing.last_error
    assert GeminiService(Settings(), client=fake_client(text="")).generate("p") is None


def test_prompt_contains_results():
    prompt = GeminiService.build_prompt({"farm": {"name": "Test Farm"}})
    assert "Test Farm" in prompt and "do not invent data" in prompt


def test_research_agent_narrative_source():
    agent = ResearchAgent(GeminiService(Settings(), client=fake_client(text="Narrative")))
    assert agent.narrative({"a": 1}) == ("Narrative", "gemini")
    assert ResearchAgent(GeminiService(Settings(gemini_api_key=""))).narrative({}) == (None, "rule-based")
