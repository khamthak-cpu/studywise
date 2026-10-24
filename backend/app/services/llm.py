
import asyncio
import logging
from functools import lru_cache
from pathlib import Path

import httpx
from ollama import AsyncClient, ResponseError

from app.config import Settings
from app.schemas import Source

log = logging.getLogger(__name__)
PROMPT_DIR = Path(__file__).resolve().parents[1] / "prompts"


class LLMError(Exception):
    """Raised when the language model cannot generate an answer."""


@lru_cache
def _prompt(name: str) -> str:
    path = PROMPT_DIR / f"{name}.txt"
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8").strip()


def _format_context(sources: list[Source], max_chars: int) -> str:
    blocks: list[str] = []
    used = 0
    max_chars = max(0, max_chars)

    for source in sources:
        meta = " | ".join(
            part
            for part in (
                source.title,
                source.section,
                f"p.{source.page}" if source.page else None,
            )
            if part
        )

        block = f"[{source.id}] {meta}\n{source.text.strip()}"

        if used + len(block) > max_chars:
            if not blocks and max_chars:
                blocks.append(block[:max_chars])
            break

        blocks.append(block)
        used += len(block)

    return "\n\n".join(blocks)


def _clean_history(
    history: list[dict[str, str]] | None,
    limit: int = 16,
) -> list[dict[str, str]]:
    """Keep recent, valid user and assistant messages."""
    if not history:
        return []

    cleaned: list[dict[str, str]] = []

    for item in history[-limit:]:
        role = item.get("role")
        content = item.get("content", "").strip()

        if role in {"user", "assistant"} and content:
            cleaned.append({"role": role, "content": content})

    # Ensure the supplied history ends with a complete exchange or
    # an assistant response, not an orphaned user message.
    return cleaned


class LLM:
    def __init__(self, settings: Settings, client: AsyncClient):
        self._s = settings
        self._client = client
        self._sem = asyncio.Semaphore(settings.max_concurrent_llm)

    def _system_prompt(
        self,
        language: str,
        simplify: bool,
        subject: str | None,
        context: str | None = None,
    ) -> str:
        parts: list[str] = [
            (
                "You are StudyWise, a patient educational tutor for "
                "Indian school students in Classes 8–12."
            ),
            (
                "Answer the student's latest question directly. "
                "Use conversation history to resolve references such as "
                "'it', 'they', 'why?', 'give an example', and "
                "'how does it differ?' when possible."
            ),
            (
                "If a follow-up has a likely meaning from the conversation, "
                "answer that meaning instead of asking for clarification. "
                "Ask a clarification question only when the meaning cannot "
                "reasonably be inferred."
            ),
            (
                "Do not narrate your reasoning, list possible interpretations, "
                "or explain what you think the student might mean. "
                "Give the answer itself."
            ),
            (
                "If the student clearly changes topics, answer the new "
                "question. Keep explanations clear, concise, and suitable "
                "for the student's level."
            ),
            (
                "Never invent citations, textbook page numbers, or claims "
                "about source passages."
            ),
        ]
        parts.extend([
            (
                "Return only the final answer to the student's question. "
                "Never output internal reasoning, planning, self-talk, "
                "word-count calculations, or commentary about how you "
                "will answer. Start directly with the answer."
            ),
            (
                "Follow requested word limits closely. If the student asks "
                "for an explanation in 30 words, provide the explanation "
                "itself, not a description of your plan."
            ),
        ])

        if subject == "math":
            prompt = _prompt("math")
            if prompt:
                parts.append(prompt)

        if subject == "coding":
            prompt = _prompt("coding")
            if prompt:
                parts.append(prompt)

        if simplify:
            prompt = _prompt("simplify")
            if prompt:
                parts.append(prompt)

        if language == "hi":
            prompt = _prompt("hindi")
            if prompt:
                parts.append(prompt)

        if context is not None:
            parts.append(
                "Use the numbered textbook passages below for textbook-specific "
                "claims. Cite supporting passages as [1], [2], etc. Do not "
                "invent citations or claim a passage supports something it "
                "does not. Use the conversation history to understand what "
                "the student is referring to. If the passages do not support "
                "a textbook-specific answer, be honest about that limitation.\n\n"
                "<context>\n"
                f"{context}\n"
                "</context>"
            )

        return "\n\n".join(parts)

    def build_direct_messages(
        self,
        question: str,
        language: str,
        simplify: bool,
        subject: str | None = None,
        history: list[dict[str, str]] | None = None,
    ) -> list[dict[str, str]]:
        messages: list[dict[str, str]] = [
            {
                "role": "system",
                "content": self._system_prompt(
                    language=language,
                    simplify=simplify,
                    subject=subject,
                ),
            }
        ]

        messages.extend(_clean_history(history))
        messages.append({
            "role": "user",
            "content": question,
            })
        return messages

    def build_messages(
        self,
        question: str,
        context: str,
        language: str,
        simplify: bool,
        subject: str | None = None,
        history: list[dict[str, str]] | None = None,
    ) -> list[dict[str, str]]:
        messages: list[dict[str, str]] = [
            {
                "role": "system",
                "content": self._system_prompt(
                    language=language,
                    simplify=simplify,
                    subject=subject,
                    context=context,
                ),
            }
        ]

        messages.extend(_clean_history(history))
        messages.append({"role": "user", "content": question})
        return messages

    async def generate(self, messages: list[dict]) -> str:
        async with self._sem:
            try:
                response = await self._client.chat(
                    model=self._s.llm_model,
                    messages=messages,
                    think=False,
                    options={
                        "temperature": self._s.temperature,
                        "num_ctx": self._s.num_ctx,
                        "num_predict": self._s.max_new_tokens,
                    },
                    keep_alive=self._s.keep_alive,
                )
            except (
                ResponseError,
                httpx.HTTPError,
                ConnectionError,
            ) as exc:
                log.exception("Ollama request failed")
                raise LLMError(f"Model unavailable: {exc}") from exc
            except TypeError as exc:
                log.exception("Ollama client compatibility error")
                raise LLMError(
                    "The installed Ollama client may not support the "
                    "'think' parameter. Update it with: "
                    "python -m pip install --upgrade ollama"
                ) from exc

        message = response.message
        content = (getattr(message, "content", None) or "").strip()

        # Remove a leaked reasoning section if the model includes one.
        if "</think>" in content:
            content = content.rsplit("</think>", 1)[-1].strip()

        if content.startswith("<think>"):
            content = ""

        if not content:
            thinking = (
                getattr(message, "thinking", None) or ""
            ).strip()

            log.warning(
                "Ollama returned empty content: model=%s, "
                "thinking_length=%d, done_reason=%s, "
                "prompt_tokens=%s, completion_tokens=%s",
                self._s.llm_model,
                len(thinking),
                getattr(response, "done_reason", None),
                getattr(response, "prompt_eval_count", None),
                getattr(response, "eval_count", None),
            )
            raise LLMError(
                "Ollama returned no final answer. Check the model, "
                "generation token limit, and backend logs."
            )

        log.info(
            "LLM answer generated: model=%s, characters=%d",
            self._s.llm_model,
            len(content),
        )
        return content

    async def warmup(self) -> None:
        try:
            response = await self._client.chat(
                model=self._s.llm_model,
                messages=[
                    {
                        "role": "user",
                        "content": "Reply with the word ready.",
                    }
                ],
                think=False,
                options={"num_predict": 8},
                keep_alive=self._s.keep_alive,
            )

            content = (
                getattr(response.message, "content", None) or ""
            ).strip()

            if content:
                log.info("LLM warmed up: model=%s", self._s.llm_model)
            else:
                log.warning(
                    "LLM warmup returned empty content: model=%s",
                    self._s.llm_model,
                )
        except Exception as exc:
            log.warning("Warmup skipped: %s", exc)
