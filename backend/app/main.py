import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from ollama import AsyncClient

from app.config import get_settings
from app.routes import ask, health, productivity
from app.services.llm import LLM, LLMError
from app.services.retriever import Retriever
from app.services.productivity import init_db

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    cfg = get_settings()
    client = AsyncClient(host=cfg.ollama_host, timeout=cfg.llm_timeout_s)
    app.state.settings = cfg
    app.state.ollama = client
    app.state.retriever = Retriever(cfg, client)
    app.state.llm = LLM(cfg, client)
    warm = asyncio.create_task(app.state.llm.warmup())  # avoid slow first request
    yield
    warm.cancel()


app = FastAPI(title="studywise", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware, allow_origins=get_settings().cors_origins,
    allow_methods=["*"], allow_headers=["*"],
)
app.include_router(ask.router)
app.include_router(health.router)
app.include_router(productivity.router)


@app.exception_handler(LLMError)
async def llm_error_handler(_: Request, exc: LLMError):
    return JSONResponse(status_code=503, content={"detail": str(exc)})