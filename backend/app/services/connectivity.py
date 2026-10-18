import asyncio
import time

_state = {"ts": 0.0, "online": False}


async def is_online(timeout: float = 1.5, ttl: float = 10.0) -> bool:
    """Cheap TCP probe, cached so /ask never pays for it twice in a row."""
    now = time.monotonic()
    if now - _state["ts"] < ttl:
        return _state["online"]
    try:
        _, writer = await asyncio.wait_for(asyncio.open_connection("1.1.1.1", 443), timeout)
        writer.close()
        await writer.wait_closed()
        online = True
    except (OSError, asyncio.TimeoutError):
        online = False
    _state.update(ts=now, online=online)
    return online