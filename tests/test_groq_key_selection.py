import httpx
import pytest

from app.services import llm_clients


class FakeResponse:
    def __init__(self, status_code: int, content: str = "ok"):
        self.status_code = status_code
        self._content = content
        self.request = httpx.Request("POST", llm_clients.GROQ_URL)
        self.response = httpx.Response(status_code, request=self.request)

    def raise_for_status(self):
        self.response.raise_for_status()

    def json(self):
        return {"choices": [{"message": {"content": self._content}}]}


class FakeClient:
    responses = []
    authorizations = []

    def __init__(self, timeout):
        self.timeout = timeout

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return False

    async def post(self, url, json, headers):
        self.authorizations.append(headers["Authorization"])
        return self.responses.pop(0)


@pytest.fixture(autouse=True)
def reset_groq_state(monkeypatch):
    monkeypatch.setattr(llm_clients.settings, "GROQ_API_KEY", "gsk_key1")
    monkeypatch.setattr(llm_clients.settings, "GROQ_API_KEY2", "gsk_key2")
    monkeypatch.setattr(llm_clients.settings, "GROQ_API_KEY3", "gsk_key3")
    monkeypatch.setattr(llm_clients, "_groq_request_counter", iter(range(100)))
    monkeypatch.setattr(llm_clients.httpx, "AsyncClient", FakeClient)
    FakeClient.responses = []
    FakeClient.authorizations = []


@pytest.mark.asyncio
async def test_groq_chat_falls_through_to_third_key():
    FakeClient.responses = [FakeResponse(429), FakeResponse(429), FakeResponse(200, "third-key")]

    result = await llm_clients.groq_chat([{"role": "user", "content": "hello"}])

    assert result == "third-key"
    assert FakeClient.authorizations == ["Bearer gsk_key1", "Bearer gsk_key2", "Bearer gsk_key3"]


@pytest.mark.asyncio
async def test_groq_chat_round_robins_starting_key():
    FakeClient.responses = [FakeResponse(200, "first"), FakeResponse(200, "second")]

    await llm_clients.groq_chat([{"role": "user", "content": "one"}])
    await llm_clients.groq_chat([{"role": "user", "content": "two"}])

    assert FakeClient.authorizations == ["Bearer gsk_key1", "Bearer gsk_key2"]


@pytest.mark.asyncio
async def test_groq_chat_skips_malformed_key(monkeypatch):
    monkeypatch.setattr(llm_clients.settings, "GROQ_API_KEY2", "not-a-groq-key")
    FakeClient.responses = [FakeResponse(429), FakeResponse(200, "third-key")]

    result = await llm_clients.groq_chat([{"role": "user", "content": "hello"}])

    assert result == "third-key"
    assert FakeClient.authorizations == ["Bearer gsk_key1", "Bearer gsk_key3"]
