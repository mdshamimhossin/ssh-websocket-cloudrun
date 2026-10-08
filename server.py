"""Standard binary WebSocket frames <-> local SSH TCP stream."""
import asyncio
import contextlib
import os
from aiohttp import web, WSMsgType

async def health(request):
    return web.Response(text="SSH WebSocket bridge running\n")

async def bridge(request):
    ws = web.WebSocketResponse(heartbeat=30, compress=False, max_msg_size=1024*1024)
    if not ws.can_prepare(request).ok:
        return web.Response(status=400, text="Use a standard WebSocket client with binary frames.\n")
    try:
        reader, writer = await asyncio.wait_for(asyncio.open_connection("127.0.0.1", 2222), 5)
    except (OSError, asyncio.TimeoutError):
        raise web.HTTPServiceUnavailable(text="SSH unavailable")
    tasks = []
    try:
        await ws.prepare(request)
        async def to_ssh():
            async for msg in ws:
                if msg.type == WSMsgType.BINARY:
                    writer.write(msg.data)
                    await writer.drain()
                elif msg.type == WSMsgType.TEXT:
                    await ws.close(code=1003, message=b"Binary frames required")
                    break
                elif msg.type == WSMsgType.ERROR:
                    break
        async def to_ws():
            while True:
                data = await reader.read(65536)
                if not data:
                    break
                await ws.send_bytes(data)
        tasks = [asyncio.create_task(to_ssh()), asyncio.create_task(to_ws())]
        done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for task in done:
            task.result()
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        writer.close()
        with contextlib.suppress(OSError):
            await writer.wait_closed()
        if ws.prepared:
            await ws.close()
    return ws

def create_app():
    app = web.Application()
    app.router.add_get("/healthz", health)
    app.router.add_get("/", bridge)
    return app

if __name__ == "__main__":
    web.run_app(create_app(), host="0.0.0.0", port=int(os.environ.get("PORT", "8080")), access_log=None)
