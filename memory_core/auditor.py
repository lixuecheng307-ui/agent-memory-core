from __future__ import annotations

from datetime import datetime, timedelta

from memory_core.models import AuditDecision, MemoryType


class MemoryAuditor:
    """Rule-based memory auditor with a stable interface for future model review."""

    SENSITIVE_WORDS = ("api key", "apikey", "secret", "token", "cookie", "密码", "密钥", "身份证", "银行卡")
    JOKE_WORDS = ("笑死", "开玩笑", "玩笑", "自嘲", "随口", "吐槽")

    def audit(
        self,
        content: str,
        project_id: str = "default",
        memory_type: MemoryType | str | None = None,
        scope: str = "project",
        source: str = "",
    ) -> AuditDecision:
        text = str(content or "").strip()
        lowered = text.lower()
        requested = self._coerce_type(memory_type)
        sensitivity = "sensitive" if any(word in lowered or word in text for word in self.SENSITIVE_WORDS) else "normal"
        if not text:
            return AuditDecision(False, requested or MemoryType.RAW_SESSION_LOG, reason="empty_content")
        if sensitivity == "sensitive":
            return AuditDecision(
                should_remember=False,
                memory_type=MemoryType.SAFETY,
                sensitivity=sensitivity,
                allow_vector=False,
                allow_context_injection=False,
                requires_user_confirmation=True,
                reason="sensitive_content_requires_user_confirmation",
                tags=["sensitive"],
            )
        if requested is not None:
            return AuditDecision(True, requested, reason="explicit_memory_type", tags=self._tags(text, requested))
        if any(word in text for word in self.JOKE_WORDS):
            return AuditDecision(
                True,
                MemoryType.EMOTION,
                allow_context_injection=False,
                expires_at=datetime.now() + timedelta(days=7),
                reason="short_lived_emotion_or_joke",
                tags=["emotion", "short_lived"],
            )
        inferred = self._infer_type(text, scope=scope, source=source)
        return AuditDecision(True, inferred, reason="rule_inferred", tags=self._tags(text, inferred))

    def _coerce_type(self, value) -> MemoryType | None:
        if isinstance(value, MemoryType):
            return value
        text = str(value or "").strip().lower()
        if not text:
            return None
        for item in MemoryType:
            if item.value == text or item.name.lower() == text:
                return item
        return None

    def _infer_type(self, text: str, scope: str, source: str) -> MemoryType:
        lowered = text.lower()
        if "喜欢" in text or "偏好" in text or "讨厌" in text:
            return MemoryType.PREFERENCE
        if "浏览器" in text or "profile" in lowered or "cdp" in lowered:
            return MemoryType.BROWSER_EXPERIENCE
        if "项目" in text or "打包" in text or "验收" in text or scope == "project":
            return MemoryType.PROJECT
        if "成功" in text or "失败" in text or "下次" in text or "任务" in text:
            return MemoryType.TASK
        if source.startswith("skill:"):
            return MemoryType.SKILL
        return MemoryType.LONG_TERM

    def _tags(self, text: str, memory_type: MemoryType) -> list[str]:
        tags = [memory_type.value]
        if "agent memory core" in text.lower():
            tags.append("agent_memory_core")
        if "rag" in text.lower() or "向量" in text:
            tags.append("rag")
        if "浏览器" in text or "profile" in text.lower() or "cdp" in text.lower():
            tags.append("browser")
        return tags
