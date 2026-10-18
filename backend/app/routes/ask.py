
import re
import time
import logging

from fastapi import APIRouter, HTTPException, Request

from app.schemas import AskRequest, AskResponse
from app.services import fallback
from app.services.connectivity import is_online
from app.services.web_search import search_web

router = APIRouter()
log = logging.getLogger(__name__)

_DEVANAGARI = re.compile(r"[\u0900-\u097F]")
_TEXTBOOK_HINTS = re.compile(
    r"\b(ncert|textbook|text book|chapter|exercise|"
    r"question number|page number|according to the book|"
    r"class \d+|grade \d+)\b",
    re.IGNORECASE,
)


def _resolve_language(req: AskRequest) -> str:
    if req.language != "auto":
        return req.language
    return "hi" if _DEVANAGARI.search(req.question) else "en"


@router.post("/ask", response_model=AskResponse)
async def ask(req: AskRequest, request: Request) -> AskResponse:
    t0 = time.perf_counter()
    st = request.app.state
    cfg, retriever, llm = st.settings, st.retriever, st.llm

    lang = _resolve_language(req)
    mode = str(req.mode).lower()

    online = False
    if mode != "offline" and cfg.web_search_enabled:
        try:
            online = await is_online()
        except Exception:
            log.warning("Connectivity check failed", exc_info=True)

    def elapsed() -> int:
        return int((time.perf_counter() - t0) * 1000)

    def needs_textbook() -> bool:
        return bool(
            req.class_level
            or _TEXTBOOK_HINTS.search(req.question)
        )

    # Qwen always gets the first chance to answer general questions.
    try:
        direct_answer = await llm.generate(
            llm.build_direct_messages(
                req.question, lang, req.simplify, req.subject
            )
        )
    except Exception as exc:
        log.exception("Direct Qwen answer failed")
        raise HTTPException(
            status_code=503,
            detail=f"Could not generate an answer with Qwen: {exc}",
        ) from exc

    needs_rag = (
        mode == "offline" and needs_textbook()
    ) or (
        direct_answer.strip().startswith("[NEED_RAG]")
    ) or (
        needs_textbook()
    )

    # General questions get Qwen's answer directly when no retrieval is needed.
    if not needs_rag and mode != "online":
        return AskResponse(
            answer=direct_answer,
            sources=[],
            confidence=0.0,
            answered_from="fallback",
            language=lang,
            online=online,
            latency_ms=elapsed(),
        )

    context = []
    confidence = 0.0
    origins = []

    # Retrieve local NCERT evidence when the question needs it.
    if needs_rag or mode == "online":
        if not retriever.ready:
            log.warning("Knowledge base is not ready; continuing without RAG")
        else:
            try:
                found = await retriever.search(
                    req.question, req.class_level, req.subject
                )
                confidence = found[0].score if found else 0.0
                if fallback.is_confident(found, cfg.min_score):
                    local_context = fallback.relevant_only(
                        found, cfg.min_score
                    )
                    context.extend(local_context)
                    if local_context:
                        origins.append("notes")
            except Exception:
                log.exception("Textbook retrieval failed")

    # Explicit online mode searches the web; auto mode uses it if Qwen
    # requested evidence and the local textbook results are insufficient.
    should_search_web = (
        online
        and mode in ("online", "auto")
        and (
            mode == "online"
            or (needs_rag and not context)
        )
    )

    if should_search_web:
        scope = " ".join(
            filter(
                None,
                [
                    f"class {req.class_level}" if req.class_level else None,
                    req.subject.replace("_", " ") if req.subject else None,
                    "NCERT" if mode == "auto" else None,
                ],
            )
        )
        try:
            web_context = await search_web(
                f"{scope} {req.question}".strip()
            )
            if web_context:
                context.extend(web_context)
                origins.append("web")
        except Exception:
            log.exception("Web search failed")

    # If no evidence is available, return Qwen's own answer rather than
    # blocking the student with a textbook-only fallback message.
    if not context:
        answer = direct_answer
        if answer.strip().startswith("[NEED_RAG]"):
            answer = (
                "I couldn't find enough supporting information to answer "
                "that confidently. Please rephrase the question or provide "
                "the relevant textbook passage."
            )
        return AskResponse(
            answer=answer,
            sources=[],
            confidence=confidence,
            answered_from="fallback",
            language=lang,
            online=online,
            latency_ms=elapsed(),
        )

    for i, source in enumerate(context, 1):
        source.id = i

    # Ask Qwen to produce the final answer using the retrieved evidence.
    try:
        answer = await llm.generate(
            llm.build_messages(
                req.question, context, lang, req.simplify, req.subject
            )
        )
        if answer.strip().startswith("[NEED_RAG]"):
            answer = direct_answer
    except Exception:
        log.exception("Evidence-based generation failed; using direct answer")
        answer = direct_answer

    answered_from = (
        "mixed" if len(set(origins)) > 1
        else origins[0] if origins
        else "fallback"
    )

    return AskResponse(
        answer=answer,
        sources=context,
        confidence=confidence,
        answered_from=answered_from,
        language=lang,
        online=online,
        latency_ms=elapsed(),
    )
