
import re
import time
import logging

from fastapi import APIRouter, HTTPException, Request

from app.schemas import AskRequest, AskResponse
from app.services import fallback, chat_history
from app.services.connectivity import is_online
from app.services.web_search import search_web
from app.services.attachments import get_selected_attachments, IMAGE_EXTENSIONS

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
    r"program|programming|function|algorithm|python|javascript|"
    r"typescript|html|css|java|sql|react|api|bug|traceback)\b",
    re.IGNORECASE,
)


def _resolve_language(req: AskRequest) -> str:
    if req.language != "auto":
        return req.language
    return "hi" if _DEVANAGARI.search(req.question) else "en"


def _is_coding_request(req: AskRequest) -> bool:
    return (
        str(req.subject or "").lower() == "coding"
        or bool(_CODING_HINTS.search(req.question))
    )


def _format_sources(sources) -> str:
    """Convert retrieved source objects into readable LLM context."""
    blocks = []

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
        blocks.append(
            f"[{source.id}] {meta}\n{source.text.strip()}"
        )

    return "\n\n".join(blocks)


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
            log.warning("Connectivity check failed", exc_info=True)

    def elapsed() -> int:
        return int((time.perf_counter() - t0) * 1000)

    def needs_textbook() -> bool:
        return bool(
            req.class_level or _TEXTBOOK_HINTS.search(req.question)
        )

    # Load earlier messages BEFORE saving the current question.
    history: list[dict[str, str]] = []
    conversation_id = req.conversation_id
    student_id = req.student_id.strip()

    if not student_id or len(student_id) > 80:
        raise HTTPException(
            status_code=400,
            detail="student_id must be 1–80 characters",
        )

    if conversation_id is not None:
        try:
            history = chat_history.get_recent_messages(
                student_id=student_id,
                conversation_id=conversation_id,
                limit=24,
            )
        except ValueError as exc:
            raise HTTPException(
                status_code=404,
                detail=str(exc),
            ) from exc

        # Persist the current question after loading prior history.
        saved = chat_history.add_message(
            student_id=student_id,
            conversation_id=conversation_id,
            role="user",
            content=req.question,
        )

        if saved is None:
            raise HTTPException(
                status_code=404,
                detail="Conversation not found",
            )

    attachment_context = ""
    if req.attachment_ids and conversation_id is None:
        raise HTTPException(400, "Create a conversation before attaching files.")
    if conversation_id is not None:
        try:
            attachments = get_selected_attachments(
                student_id, conversation_id, req.attachment_ids
            )
            attachment_blocks = []
            for attachment in attachments:
                filename = attachment["filename"]
                extracted = (attachment.get("extracted_text") or "").strip()
                if attachment["extension"] in IMAGE_EXTENSIONS:
                    description = await llm.describe_image(attachment["storage_path"])
                    attachment_blocks.append(
                        f"[Uploaded image: {filename}]\n{description}"
                    )
                elif extracted:
                    attachment_blocks.append(
                        f"[Uploaded document: {filename}]\n{extracted}"
                    )
                else:
                    attachment_blocks.append(
                        f"[Uploaded document: {filename}]\nNo extractable text was found. "
                        "It may be a scanned PDF; OCR is not configured for this file yet."
                    )
            attachment_context = "\n\n".join(attachment_blocks)[:24000]
        except HTTPException:
            raise
        except Exception as exc:
            log.exception("Could not process uploaded attachment")
            raise HTTPException(
                status_code=503,
                detail=f"Could not process an uploaded file: {exc}",
            ) from exc

    def save_assistant_answer(answer: str) -> None:
        """Persist the final answer once for this request."""
        if conversation_id is None:
            return

        saved = chat_history.add_message(
            student_id=student_id,
            conversation_id=conversation_id,
            role="assistant",
            content=answer,
        )

        if saved is None:
            raise HTTPException(
                status_code=404,
                detail="Conversation not found",
            )

    # Generate a direct answer with conversation history.
    try:
        direct_messages = llm.build_direct_messages(
            question=req.question,
            language=lang,
            simplify=req.simplify,
            subject=llm_subject,
            history=history,
            attachment_context=attachment_context or None,
        )
        direct_answer = await llm.generate(direct_messages)

    except Exception as exc:
        log.exception("Direct LLM answer failed")
        raise HTTPException(
            status_code=503,
            detail=f"Could not generate an answer: {exc}",
        ) from exc

    needs_rag = not attachment_context and not is_coding and (
        (mode == "offline" and needs_textbook())
        or direct_answer.strip().startswith("[NEED_RAG]")
        or needs_textbook()
    )

    # Return direct answers for general questions unless online
    # mode was explicitly requested.
    if not needs_rag and mode != "online":
        save_assistant_answer(direct_answer)
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

    # Search online when explicitly requested, or when auto mode
    # needs evidence not found in the local textbook index.
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

    # No supporting evidence: use the direct answer.
    if not context:
        answer = direct_answer

        if answer.strip().startswith("[NEED_RAG]"):
            answer = (
                "I couldn't find enough supporting information "
                "to answer confidently. Please rephrase your "
                "question or provide the relevant textbook passage."
            )

        save_assistant_answer(answer)
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

    # Pass a text representation of sources and the same conversation
    # history to the evidence-based answer generation path.
    try:
        context_text = _format_sources(context)

        messages = llm.build_messages(
            question=req.question,
            context=context_text,
            language=lang,
            simplify=req.simplify,
            subject=llm_subject,
            history=history,
            attachment_context=attachment_context or None,
        )

        answer = await llm.generate(messages)

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

    save_assistant_answer(answer)

    return AskResponse(
        answer=answer,
        sources=context,
        confidence=confidence,
        answered_from=answered_from,
        language=lang,
        online=online,
        latency_ms=elapsed(),
    )
