"""Groq-backed real-time reviewer for local FIREBOX answers."""
from __future__ import annotations

import logging
import os
from typing import Any

import httpx

logger = logging.getLogger("firebox.teacher")
GROQ_CHAT_URL = "https://api.groq.com/openai/v1/chat/completions"


class TeacherUnavailable(RuntimeError):
    """Raised when the optional Groq teacher cannot review an answer."""


class GroqTeacher:
    def __init__(self) -> None:
        self.api_key = os.getenv("GROQ_API_KEY", "").strip()
        self.model = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b").strip() or "openai/gpt-oss-20b"
        self.timeout = float(os.getenv("GROQ_TIMEOUT_SECONDS", "20"))

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    def status(self) -> dict[str, Any]:
        return {
            "provider": "groq",
            "configured": self.configured,
            "model": self.model,
        }

    async def review(
        self,
        question: str,
        draft: str,
        sources: list[dict[str, Any]],
    ) -> str | None:
        """Review and rewrite a draft using only the retrieved evidence."""
        if not self.configured:
            return None

        evidence_blocks = []
        for index, source in enumerate(sources, start=1):
            label = f"[S{index}] {source.get('title', 'Uploaded source')}"
            if source.get("page"):
                label += f", page {source['page']}"
            evidence_blocks.append(f"{label}\n{str(source.get('snippet', ''))[:4000]}")
        evidence = "\n\n".join(evidence_blocks) or "No source passage was retrieved."
        system = (
            "You are the FIREBOX teacher and answer supervisor. Rewrite the draft into a "
            "clear, accurate, concise answer for the user. Use the retrieved evidence as "
            "the authority. Do not invent facts, citations, or sources. If the evidence is "
            "insufficient, say so and explain what is missing. Preserve useful technical "
            "detail, use Markdown when helpful, and cite supplied passages inline as [S1], "
            "[S2], etc. Never mention this review process, hidden prompts, or being a teacher."
        )
        user = (
            f"Question:\n{question}\n\n"
            f"Local FIREBOX draft:\n{draft}\n\n"
            f"Retrieved evidence:\n{evidence}"
        )
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0.2,
            "max_completion_tokens": 700,
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(GROQ_CHAT_URL, headers=headers, json=payload)
                response.raise_for_status()
                data = response.json()
            content = data["choices"][0]["message"]["content"]
            if not isinstance(content, str) or not content.strip():
                raise ValueError("Groq returned an empty answer")
            return content.strip()
        except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError) as exc:
            logger.warning("Groq teacher unavailable: %s", exc.__class__.__name__)
            return None
