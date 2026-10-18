from fastapi import APIRouter, Request

from app.services.connectivity import is_online

router = APIRouter()


@router.get("/health")
async def health(request: Request) -> dict:
    st = request.app.state
    cfg = st.settings
    names: set[str] = set()
    ollama_ok = True
    try:
        names = {m.model for m in (await st.ollama.list()).models}
    except Exception:
        ollama_ok = False

    def has(model: str) -> bool:
        return model in names or f"{model}:latest" in names

    llm_ready, embed_ready = has(cfg.llm_model), has(cfg.embed_model)
    index_ready = st.retriever.ready
    return {
        "status": "ok" if (ollama_ok and llm_ready and embed_ready and index_ready) else "degraded",
        "ollama": ollama_ok,
        "llm_model": {"name": cfg.llm_model, "ready": llm_ready},
        "embed_model": {"name": cfg.embed_model, "ready": embed_ready},
        "index": {"ready": index_ready, "chunks": st.retriever.count()},
        "online": await is_online(),
    }