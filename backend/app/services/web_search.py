import asyncio
import logging

from app.schemas import Source

log = logging.getLogger(__name__)


async def search_web(query: str, max_results: int = 3, timeout: float = 6.0) -> list[Source]:
    """Optional online layer. Never raises: returns [] on any failure."""
    try:
        from ddgs import DDGS
    except ImportError:
        return []

    def _run():
        with DDGS() as d:
            return list(d.text(query, max_results=max_results))

    try:
        rows = await asyncio.wait_for(asyncio.to_thread(_run), timeout)
    except Exception as e:
        log.exception("Web search failed")
        return []

    return [
        Source(kind="web", title=r.get("title", "Web"), url=r.get("href"),
               snippet=r.get("body", "")[:200], text=r.get("body", ""))
        for r in rows if r.get("body")
    ]