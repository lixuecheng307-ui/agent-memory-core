import os

import pytest

from memory_core import OpenAICompatibleEmbeddingProvider


def test_openai_compatible_provider_requires_explicit_key(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "env-value-should-not-be-read")

    with pytest.raises(ValueError):
        OpenAICompatibleEmbeddingProvider(api_key="", base_url="https://example.test/v1", model="embed")


def test_openai_compatible_provider_uses_mocked_http_only(monkeypatch):
    calls = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return b'{"data":[{"embedding":[6,8]}]}'

    def fake_urlopen(request, timeout):
        calls["url"] = request.full_url
        calls["auth"] = dict(request.header_items())["Authorization"]
        calls["body"] = request.data.decode("utf-8")
        calls["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    provider = OpenAICompatibleEmbeddingProvider(
        api_key="unit",
        base_url="https://example.test/v1",
        model="embed-test",
        timeout=3,
    )

    vector = provider.embed("hello")

    assert os.environ.get("OPENAI_API_KEY") != "unit"
    assert calls["url"] == "https://example.test/v1/embeddings"
    assert calls["auth"] == "Bearer unit"
    assert '"model": "embed-test"' in calls["body"]
    assert calls["timeout"] == 3
    assert vector == [0.6, 0.8]
