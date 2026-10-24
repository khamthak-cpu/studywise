
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

_CODING_HINTS = re.compile(
    r"\b(write|generate|debug|fix|implement|code|coding|"
    r"program|programming|function|algorithm|"
    r"python|javascript|typescript|html|css|"
    r"java|sql|react|api|bug|traceback|"
    r"javascript|typescript|c\+\+)\b",
    re.IGNORECASE,
)


def _resolve_language(req: AskRequest) -> str:
    if req.language != "auto":
        return req.language

    return "hi" if _DEVANAGARI.search(req.question) else "en"


def _is_coding_request(req: AskRequest) -> bool:
    subject = str(req.subject or "").lower()

    return (
        subject == "coding"
        or bool(_CODING_HINTS.search(req.question))
    )


@router.post("/ask", response_model=AskResponse)
async def ask(req: AskRequest, request: Request) -> AskResponse:
    t0 = time.perf_counter()

    st = request.app.state
    cfg = st.settings
    retriever = st.retriever
    llm = st.llm

    lang = _resolve_language(req)
    mode = str(req.mode).lower()

    is_coding = _is_coding_request(req)
    llm_subject = "coding" if is_coding else req.subject

    online = False

    if mode != "offline" and cfg.web_search_enabled:
        try:
            online = await is_online()
        except Exception:
            log.warning(
                "Connectivity check failed",
                exc_info=True,
            )

    def elapsed() -> int:
        return int((time.perf_counter() - t0) * 1000)

    def needs_textbook() -> bool:
        return bool(
            req.class_level
            or _TEXTBOOK_HINTS.search(req.question)
        )

    # Generate a direct answer first.
    try:
        direct_answer = await llm.generate(
            llm.build_direct_messages(
                req.question,
                lang,
                req.simplify,
                llm_subject,
            )
        )
    except Exception as exc:
        log.exception("Direct LLM answer failed")
        raise HTTPException(
            status_code=503,
            detail=f"Could not generate an answer: {exc}",
        ) from exc

    # Coding requests should not trigger textbook retrieval
    # merely because of generic coding keywords.
    needs_rag = not is_coding and (
        (mode == "offline" and needs_textbook())
        or direct_answer.strip().startswith("[NEED_RAG]")
        or needs_textbook()
    )

    # Return direct answers for general questions unless
    # online mode was explicitly requested.
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

    # Retrieve local textbook evidence when needed.
    if needs_rag or mode == "online":
        if not retriever.ready:
            log.warning(
                "Knowledge base is not ready; continuing without RAG"
            )
        else:
            try:
                found = await retriever.search(
                    req.question,
                    req.class_level,
                    req.subject,
                )

                confidence = found[0].score if found else 0.0

                if fallback.is_confident(found, cfg.min_score):
                    local_context = fallback.relevant_only(
                        found,
                        cfg.min_score,
                    )

                    context.extend(local_context)

                    if local_context:
                        origins.append("notes")

            except Exception:
                log.exception("Textbook retrieval failed")

    # Search the web in explicit online mode, or in auto mode
    # when evidence is needed but local textbook results are absent.
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
                    (
                        f"class {req.class_level}"
                        if req.class_level
                        else None
                    ),
                    (
                        req.subject.replace("_", " ")
                        if req.subject
                        else None
                    ),
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

    # If no supporting evidence is available, use the direct answer.
    if not context:
        answer = direct_answer

        if answer.strip().startswith("[NEED_RAG]"):
            answer = (
                "I couldn't find enough supporting information "
                "to answer confidently. Please rephrase your "
                "question or provide the relevant textbook passage."
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

    # Generate a final answer grounded in retrieved evidence.
    try:
        answer = await llm.generate(
            llm.build_messages(
                req.question,
                context,
                lang,
                req.simplify,
                llm_subject,
            )
        )

        if answer.strip().startswith("[NEED_RAG]"):
            answer = direct_answer

    except Exception:
        log.exception(
            "Evidence-based generation failed; using direct answer"
        )
        answer = direct_answer

    answered_from = (
        "mixed"
        if len(set(origins)) > 1
        else origins[0]
        if origins
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
