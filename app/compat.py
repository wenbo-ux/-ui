"""后端兼容层：优先 FastAPI，缺失时降级到 Starlette。

两者共用同一套 handler（都接收 Starlette 的 Request、返回 Response），
所以业务代码只需要写一遍。FastAPI 额外送 /docs 交互文档。
"""
from __future__ import annotations

import inspect
from contextlib import asynccontextmanager

from typing import Any, Callable

try:  # 优先 FastAPI（自带 /docs）
    from fastapi import FastAPI as _App  # type: ignore
    from fastapi.responses import (  # type: ignore
        FileResponse,
        HTMLResponse,
        JSONResponse,
        Response,
    )

    BACKEND = "fastapi"
except ImportError:  # pragma: no cover - Termux 上常见
    from starlette.applications import Starlette as _App  # type: ignore
    from starlette.responses import (  # type: ignore
        FileResponse,
        HTMLResponse,
        JSONResponse,
        Response,
    )

    BACKEND = "starlette"

from starlette.requests import Request  # noqa: E402
from starlette.routing import Route  # noqa: E402

__all__ = [
    "BACKEND",
    "Request",
    "Response",
    "JSONResponse",
    "HTMLResponse",
    "FileResponse",
    "build_app",
]


def build_app(routes: list[Route], on_startup: Callable[[], Any] | None = None,
              on_shutdown: Callable[[], Any] | None = None, **kwargs: Any) -> Any:
    """构造 ASGI app。FastAPI 走 add_api_route，Starlette 走 routes 列表。

    注意：Starlette 新版已移除 on_startup/on_shutdown 参数，这里统一用 lifespan。
    """
    lifespan = None
    if on_startup or on_shutdown:
        @asynccontextmanager
        async def lifespan(_app: Any):  # type: ignore[no-redef]
            await _maybe_await(on_startup)
            yield
            await _maybe_await(on_shutdown)

    if BACKEND == "fastapi":
        app = _App(lifespan=lifespan, **kwargs)  # type: ignore[call-arg]
        for r in routes:
            app.add_api_route(
                r.path,
                r.endpoint,
                methods=list(r.methods or ["GET"]),
                include_in_schema=r.path.startswith("/api"),
                name=getattr(r, "name", None),
            )
        return app

    return _App(routes=routes, lifespan=lifespan, **{
        k: v for k, v in kwargs.items() if k in ("debug", "middleware", "exception_handlers")
    })


async def _maybe_await(fn: Callable[[], Any] | None) -> None:
    if fn is None:
        return
    result = fn()
    if inspect.isawaitable(result):
        await result
