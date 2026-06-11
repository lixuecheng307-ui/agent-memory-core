from __future__ import annotations

import hashlib
import json
import math
import re
import urllib.request
from collections import Counter


class DeterministicEmbeddingProvider:
    """Offline embedding provider for local acceptance and private deployments.

    It creates real numeric vectors and cosine-searchable semantic buckets without
    network calls. Production deployments can replace this class with an API or
    model-backed provider that exposes the same embed(text) method.
    """

    def __init__(self, dimensions: int = 192):
        self.dimensions = int(dimensions)

    def embed(self, text: str) -> list[float]:
        tokens = self._tokens(text)
        counts: Counter[str] = Counter()
        for token in tokens:
            counts[token] += 1.0
            counts[f"tok:{token}"] += 0.7
            for bucket in self._semantic_buckets(token):
                counts[f"sem:{bucket}"] += 1.8
        vector = [0.0] * self.dimensions
        for token, weight in counts.items():
            index = self._index(token)
            sign = -1.0 if self._index("sign:" + token) % 2 else 1.0
            vector[index] += float(weight) * sign
        norm = math.sqrt(sum(value * value for value in vector)) or 1.0
        return [value / norm for value in vector]

    def _index(self, token: str) -> int:
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        return int.from_bytes(digest[:4], "big") % self.dimensions

    def _tokens(self, text: str) -> list[str]:
        value = str(text or "").lower()
        raw = re.findall(r"[a-z0-9_]+|[\u4e00-\u9fff]", value)
        tokens = [item for item in raw if item.strip()]
        words = re.findall(r"[a-z0-9_]{2,}", value)
        tokens.extend(words)
        compact = "".join(re.findall(r"[\u4e00-\u9fff]", value))
        tokens.extend(compact[i : i + 2] for i in range(max(0, len(compact) - 1)))
        tokens.extend(compact[i : i + 3] for i in range(max(0, len(compact) - 2)))
        return tokens

    def _semantic_buckets(self, token: str) -> list[str]:
        groups = {
            "minimal_ui": {"极简", "简洁", "干净", "清爽", "克制", "简约", "minimal", "clean"},
            "project_status": {"项目", "进度", "阶段", "状态", "验收", "打包", "发布", "project"},
            "browser_automation": {"浏览器", "登录态", "profile", "cdp", "chrome", "自动化", "网页"},
            "memory_rag": {"记忆", "rag", "向量", "召回", "embedding", "chroma", "语义"},
            "emotion_short": {"焦虑", "难受", "开心", "生气", "累", "情绪", "吐槽", "玩笑"},
            "sensitive": {"key", "api", "密码", "token", "secret", "cookie", "密钥"},
        }
        return [name for name, members in groups.items() if token in members]


class OpenAICompatibleEmbeddingProvider:
    """Embedding provider for OpenAI-compatible `/embeddings` APIs.

    The provider never reads environment variables by itself. Callers must pass
    an API key explicitly, which keeps key ownership in the host application.
    """

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.openai.com/v1",
        model: str = "text-embedding-3-small",
        timeout: float = 30.0,
    ):
        self.api_key = str(api_key or "")
        self.base_url = str(base_url or "").rstrip("/")
        self.model = str(model or "")
        self.timeout = float(timeout)
        if not self.api_key:
            raise ValueError("api_key is required for OpenAICompatibleEmbeddingProvider")
        if not self.base_url:
            raise ValueError("base_url is required for OpenAICompatibleEmbeddingProvider")
        if not self.model:
            raise ValueError("model is required for OpenAICompatibleEmbeddingProvider")

    def embed(self, text: str) -> list[float]:
        payload = json.dumps({"model": self.model, "input": str(text or "")}).encode("utf-8")
        request = urllib.request.Request(
            f"{self.base_url}/embeddings",
            data=payload,
            method="POST",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
        )
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            body = json.loads(response.read().decode("utf-8"))
        try:
            embedding = body["data"][0]["embedding"]
        except Exception as exc:
            raise RuntimeError("embedding response did not contain data[0].embedding") from exc
        vector = [float(value) for value in embedding]
        norm = math.sqrt(sum(value * value for value in vector)) or 1.0
        return [value / norm for value in vector]
