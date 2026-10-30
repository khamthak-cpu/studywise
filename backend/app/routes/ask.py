
import re
import time
import logging

from fastapi import APIRouter, HTTPException, Request

from app.schemas import AskRequest, AskResponse
from app.services import fallback, chat_history
from app.services.connectivity import is_online
from app.services.web_search import search_web
from app.services.attachments import (
    get_selected_attachments,
    IMAGE_EXTENSIONS,
)

router = APIRouter()
log = logging.getLogger(__name__)

_DEVANAGARI = re.compile(r"[\u0900-\u097F]")

_TEXTBOOK_HINTS = re.compile(
    r"\b(ncert|textbook|text book|chapter|exercise|"
    r"question number|page number|according to the book|"
    r"class \d+|grade \d+)\b",
    re.IGNORECASE,
)

_FOLLOWUP_ONLY = re.compile(
    r"^(why|how|what about that|explain|elaborate|"
    r"give an example|more details)[?.!\s]*$",
    re.IGNORECASE,
)

EDUCATION_LABELS = {
    "primary": "Primary School",
    "middle": "Middle School",
    "secondary": "Secondary School",
    "higher_secondary": "Higher Secondary",
    "college": "College / Undergraduate",
}


# ==================================================
# LANGUAGE
# ==================================================

def _resolve_language(req: AskRequest) -> str:
    if req.language != "auto":
        return req.language

    return "hi" if _DEVANAGARI.search(req.question) else "en"


# ==================================================
# CODING CLASSIFICATION
# ==================================================

def _is_coding_request(req: AskRequest) -> bool:
    # Coding is explicitly enabled by the user.
    # Do not classify ordinary study questions as coding.

    return bool(
        req.coding_mode
        or str(req.subject or "").lower() == "coding"
    )


# ==================================================
# FOLLOW-UP QUERY REWRITING
# ==================================================

def _standalone_query(
    question: str,
    history: list[dict[str, str]],
) -> str:

    q = question.strip()

    if not _FOLLOWUP_ONLY.match(q) or not history:
        return q

    previous_user = next(
        (
            m.get("content", "").strip()
            for m in reversed(history)
            if m.get("role") == "user"
            and m.get("content", "").strip()
        ),
        "",
    )

    previous_assistant = next(
        (
            m.get("content", "").strip()
            for m in reversed(history)
            if m.get("role") == "assistant"
            and m.get("content", "").strip()
        ),
        "",
    )

    if not previous_user:
        return q

    return (
        f"Regarding the previous question: {previous_user}\n"
        f"Follow-up: {q}\n"
        f"Previous answer context: {previous_assistant[:500]}"
    )


# ==================================================
# SOURCE FORMATTING
# ==================================================

def _format_sources(sources) -> str:

    blocks = []

    for source in sources:

        metadata = " | ".join(
            part
            for part in (
                source.title,
                source.section,
                f"p.{source.page}" if source.page else None,
            )
            if part
        )

        blocks.append(
            f"[{source.id}] {metadata}\n"
            f"{source.text.strip()}"
        )

    return "\n\n".join(blocks)


# ==================================================
# EDUCATION CONTEXT
# ==================================================

def _education_context(req: AskRequest) -> str:

    if req.education_level == "college":

        return (
            "Student education level: College / Undergraduate.\n"
            f"Degree: {req.degree or 'Not specified'}.\n"
            f"Academic year: {req.study_year or 'Not specified'}.\n"
            f"Subject: {req.subject or 'Not specified'}.\n"
            "Use appropriate undergraduate terminology, "
            "academic depth, explanations and examples. "
            "Do not oversimplify university-level concepts."
        )

    level = EDUCATION_LABELS.get(
        req.education_level,
        "Secondary School",
    )

    return (
        f"Student education level: {level}.\n"
        f"Class: {req.class_level or 'Not specified'}.\n"
        f"Subject: {req.subject or 'Not specified'}.\n"
        "Adjust vocabulary, examples, mathematical depth "
        "and explanation complexity to this student's level."
    )


# ==================================================
# MAIN ASK ENDPOINT
# ==================================================

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

    # --------------------------------------------------
    # INTERNET CONNECTION
    # --------------------------------------------------

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

    # --------------------------------------------------
    # DETERMINE STUDY QUESTION
    # --------------------------------------------------

    def needs_textbook() -> bool:

        return bool(
            req.class_level is not None
            or req.education_level != "secondary"
            or _TEXTBOOK_HINTS.search(req.question)
        )

    education_context = _education_context(req)

    def contextual_question(question: str) -> str:

        return (
            f"{education_context}\n\n"
            "Answer at the appropriate academic level.\n\n"
            f"Question: {question}"
        )

    # --------------------------------------------------
    # CONVERSATION HISTORY
    # --------------------------------------------------

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

        # Save the current question after loading history.

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

    # --------------------------------------------------
    # ATTACHMENT PROCESSING
    # --------------------------------------------------

    attachment_context = ""

    if req.attachment_ids and conversation_id is None:

        raise HTTPException(
            status_code=400,
            detail="Create a conversation before attaching files.",
        )

    if conversation_id is not None:

        try:

            attachments = get_selected_attachments(
                student_id,
                conversation_id,
                req.attachment_ids,
            )

            attachment_blocks = []

            for attachment in attachments:

                filename = attachment["filename"]

                extracted = (
                    attachment.get("extracted_text") or ""
                ).strip()

                if attachment["extension"] in IMAGE_EXTENSIONS:

                    description = await llm.describe_image(
                        attachment["storage_path"]
                    )

                    attachment_blocks.append(
                        f"[Uploaded image: {filename}]\n"
                        f"{description}"
                    )

                elif extracted:

                    attachment_blocks.append(
                        f"[Uploaded document: {filename}]\n"
                        f"{extracted}"
                    )

                else:

                    attachment_blocks.append(
                        f"[Uploaded document: {filename}]\n"
                        "No extractable text was found. "
                        "It may be a scanned PDF; OCR is not configured."
                    )

            attachment_context = (
                "\n\n".join(attachment_blocks)[:24000]
            )

        except HTTPException:
            raise

        except Exception as exc:

            log.exception(
                "Could not process uploaded attachment"
            )

            raise HTTPException(
                status_code=503,
                detail=f"Could not process uploaded file: {exc}",
            ) from exc

    # --------------------------------------------------
    # SAVE FINAL ANSWER
    # --------------------------------------------------

    def save_assistant_answer(answer: str) -> None:

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

    # --------------------------------------------------
    # DIRECT ANSWER GENERATION
    # --------------------------------------------------

    def direct_messages(question_text: str | None = None):

        return llm.build_direct_messages(
            question=contextual_question(
                question_text or req.question
            ),
            language=lang,
            simplify=req.simplify,
            subject=llm_subject,
            history=history,
            attachment_context=attachment_context or None,
        )

    # --------------------------------------------------
    # RETRIEVAL DECISION
    # --------------------------------------------------

    needs_rag = (
        not attachment_context
        and not is_coding
        and needs_textbook()
    )

    # --------------------------------------------------
    # SIMPLE NON-STUDY QUESTIONS
    # --------------------------------------------------

    if not needs_rag and mode != "online":

        try:

            answer = await llm.generate(
                direct_messages()
            )

        except Exception as exc:

            log.exception(
                "Direct LLM answer failed"
            )

            raise HTTPException(
                status_code=503,
                detail=f"Could not generate an answer: {exc}",
            ) from exc

        save_assistant_answer(answer)

        return AskResponse(
            answer=answer,
            sources=[],
            confidence=0.0,
            answered_from="model",
            language=lang,
            online=online,
            latency_ms=elapsed(),
        )

    # ==================================================
    # RETRIEVAL FIRST
    # ==================================================

    context = []

    confidence = 0.0

    origins = []

    # --------------------------------------------------
    # TEXTBOOK RETRIEVAL
    # --------------------------------------------------

    if needs_rag or mode == "online":

        if not retriever.ready:

            log.warning(
                "Knowledge base is not ready."
            )

        elif req.education_level == "college":

            # IMPORTANT:
            # The existing collection is an NCERT school index.
            # It does not contain degree/year metadata.
            #
            # Do not use school textbook passages as if they
            # were college textbook evidence.
            #
            # A separate college index is required for
            # grounded undergraduate answers.

            log.info(
                "College selected. Existing NCERT school index "
                "cannot establish college-level provenance."
            )

        else:

            try:

                standalone = _standalone_query(
                    req.question,
                    history,
                )

                retrieval_query = contextual_question(
                    standalone
                )

                found = await retriever.search(
                    retrieval_query,
                    req.class_level,
                    req.subject,
                )

                confidence = (
                    found[0].score if found else 0.0
                )

                if fallback.is_confident(
                    found,
                    cfg.min_score,
                ):

                    local_context = fallback.relevant_only(
                        found,
                        cfg.min_score,
                    )

                    context.extend(local_context)

                    if local_context:
                        origins.append("notes")

            except Exception:

                log.exception(
                    "Textbook retrieval failed"
                )

    # --------------------------------------------------
    # WEB SEARCH
    # --------------------------------------------------

    should_search_web = (
        online
        and mode in ("online", "auto")
        and (
            mode == "online"
            or (needs_rag and not context)
        )
    )

    if should_search_web:

        if req.education_level == "college":

            education_scope = (
                f"{req.degree or 'undergraduate'} "
                f"year {req.study_year or ''}"
            )

        else:

            education_scope = (
                f"class {req.class_level}"
                if req.class_level is not None
                else EDUCATION_LABELS[req.education_level]
            )

        scope = " ".join(
            filter(
                None,
                [
                    education_scope,
                    (
                        req.subject.replace("_", " ")
                        if req.subject
                        else None
                    ),
                    "NCERT" if mode == "auto"
                    and req.education_level != "college"
                    else None,
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

            log.exception(
                "Web search failed"
            )

    # ==================================================
    # NO SUPPORTING SOURCES
    # ==================================================

    if not context:

        if req.education_level == "college":

            fallback_instruction = (
                "No college textbook evidence is currently indexed. "
                "Start by saying: 'No indexed college textbook source "
                "was found.' Then provide a clearly labelled "
                "'General undergraduate explanation' using general "
                "knowledge. Do not claim the answer comes from a "
                "college textbook or invent citations."
            )

        else:

            fallback_instruction = (
                "The textbook retrieval did not find supporting "
                "passages for this question. Start by saying: "
                "'Not found in the selected textbook.' Then give "
                "a clearly labelled 'General explanation' using "
                "general knowledge. Do not invent textbook citations."
            )

        messages = direct_messages(
            f"{fallback_instruction}\n\n"
            f"Question: {req.question}"
        )

        try:

            answer = await llm.generate(messages)

        except Exception as exc:

            log.exception(
                "General fallback generation failed"
            )

            raise HTTPException(
                status_code=503,
                detail=f"Could not generate an answer: {exc}",
            ) from exc

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

    # ==================================================
    # GROUNDED ANSWER GENERATION
    # ==================================================

    for index, source in enumerate(context, 1):

        source.id = index

    try:

        context_text = _format_sources(context)

        messages = llm.build_messages(
            question=contextual_question(
                _standalone_query(req.question, history)
            ),
            context=context_text,
            language=lang,
            simplify=req.simplify,
            subject=llm_subject,
            history=history,
            attachment_context=attachment_context or None,
        )

        answer = await llm.generate(messages)

        if answer.strip().startswith("[NEED_RAG]"):

            answer = (
                "The retrieved passages do not support a reliable "
                "answer. Please check the cited section or share "
                "the relevant textbook page."
            )

    except Exception as exc:

        log.exception(
            "Evidence-based generation failed"
        )

        raise HTTPException(
            status_code=503,
            detail=f"Could not generate a grounded answer: {exc}",
        ) from exc

    # ==================================================
    # ANSWER PROVENANCE
    # ==================================================

    answered_from = (
        "mixed"
        if len(set(origins)) > 1
        else origins[0]
        if origins
        else "fallback"
    )

    # ==================================================
    # SAVE AND RETURN
    # ==================================================

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
