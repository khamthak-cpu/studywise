
import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from ollama import AsyncClient

from app.config import get_settings
from app.routes import ask, health, productivity, history
from app.services.llm import LLM, LLMError
from app.services.retriever import Retriever
from app.services.productivity import init_db
from app.services.chat_history import init_history_db


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize databases
    init_db()
    init_history_db()

    # Initialize application services
    cfg = get_settings()

    client = AsyncClient(
        host=cfg.ollama_host,
        timeout=cfg.llm_timeout_s,
    )

    app.state.settings = cfg
    app.state.ollama = client
    app.state.retriever = Retriever(cfg, client)
    app.state.llm = LLM(cfg, client)

    # Warm up the language model in the background
    warm = asyncio.create_task(app.state.llm.warmup())

    try:
        yield
    finally:
        warm.cancel()
        await asyncio.gather(warm, return_exceptions=True)


app = FastAPI(
    title="StudyWise",
    version="0.1.0",
    lifespan=lifespan,
)

# Configure frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API routers
app.include_router(ask.router)
app.include_router(health.router)
app.include_router(productivity.router)
app.include_router(history.router)


# Handle language-model errors
@app.exception_handler(LLMError)
async def llm_error_handler(
    request: Request,
    exc: LLMError,
):
    logging.getLogger(__name__).error(
        "Language model error: %s",
        exc,
    )

    return JSONResponse(
        status_code=503,
        content={"detail": str(exc)},
    )
