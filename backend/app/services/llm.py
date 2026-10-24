
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
    pass


@lru_cache
def _prompt(name: str) -> str:
    return (PROMPT_DIR / f"{name}.txt").read_text(
        encoding="utf-8"
    ).strip()


def _format_context(sources: list[Source], max_chars: int) -> str:
    blocks = []
    used = 0

    for s in sources:
        meta = " | ".join(
            p
            for p in (
                s.title,
                s.section,
                f"p.{s.page}" if s.page else None,
            )
            if p
        )

        block = f"[{s.id}] {meta}\n{s.text.strip()}"

        if used + len(block) > max_chars and blocks:
            break

        blocks.append(block)
        used += len(block)

    return "\n\n".join(blocks)


class LLM:
    def __init__(self, settings: Settings, client: AsyncClient):
        self._s = settings
        self._client = client
        self._sem = asyncio.Semaphore(settings.max_concurrent_llm)

   
    def build_direct_messages(
        self,
        question: str,
        language: str,
        simplify: bool,
        subject: str | None = None,
    ) -> list[dict]:
        system = [
            "You are StudyWise, a helpful educational assistant.",
            "Answer the student's question using your own learned knowledge.",
            "Do not require textbook context to answer general questions.",
            "If you genuinely cannot answer reliably, begin your response "
            "with [NEED_RAG] and briefly explain what information is missing. "
            "Do not use this marker merely because the question is difficult.",
            "Never invent facts, citations, or textbook page numbers.",
        ]

        if subject == "math":
            system.append(_prompt("math"))

        if subject == "coding":
            system.append(_prompt("coding"))    

        if simplify:
            system.append(_prompt("simplify"))

        if language == "hi":
            system.append(_prompt("hindi"))

        return [
            {"role": "system", "content": "\n\n".join(system)},
            {"role": "user", "content": question},
        ]


    async def generate(self, messages: list[dict]) -> str:
        async with self._sem:
            try:
                res = await self._client.chat(
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

            except (ResponseError, httpx.HTTPError, ConnectionError) as e:
                log.exception("Ollama request failed")
                raise LLMError(f"Model unavailable: {e}") from e

            except TypeError as e:
                log.exception("Ollama client compatibility error")
                raise LLMError(
                    "The installed Ollama Python client may not support "
                    "the think parameter. Update it using: "
                    "python -m pip install --upgrade ollama"
                ) from e

        message = res.message
        content = (getattr(message, "content", None) or "").strip()

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
                getattr(res, "done_reason", None),
                getattr(res, "prompt_eval_count", None),
                getattr(res, "eval_count", None),
            )

            raise LLMError(
                "Ollama returned no final answer. Check the configured "
                "model, generation token limit, and backend logs."
            )

        log.info(
            "LLM answer generated: model=%s, characters=%d",
            self._s.llm_model,
            len(content),
        )

        return content

    async def warmup(self) -> None:
        try:
            res = await self._client.chat(
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
                getattr(res.message, "content", None) or ""
            ).strip()

            if content:
                log.info(
                    "LLM warmed up: model=%s",
                    self._s.llm_model,
                )
            else:
                log.warning(
                    "LLM warmup returned empty content: model=%s",
                    self._s.llm_model,
                )

        except Exception as e:
            log.warning("Warmup skipped: %s", e)
