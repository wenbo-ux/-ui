"""HTTP 路由。全部用 Starlette 的 Request/Response，两个后端都能跑。"""
from __future__ import annotations

import platform
import shutil
import sys
import time
from datetime import datetime
from typing import Any

from . import compat
from .compat import HTMLResponse, JSONResponse, Request, Response
from .config import settings
from .db import Store

store = Store(settings.db_path)
START_TS = time.time()


# ------------------------------------------------------------------ helpers
def _guard(request: Request) -> Response | None:
    """简单 token 校验。APP_TOKEN 为空时直接放行。"""
    if not settings.token:
        return None
    supplied = request.query_params.get("token") or request.headers.get("x-token", "")
    if supplied == settings.token:
        return None
    return JSONResponse({"ok": False, "error": "unauthorized"}, status_code=401)


def _json_ok(data: Any = None, status_code: int = 200, **extra: Any) -> JSONResponse:
    payload: dict[str, Any] = {"ok": True}
    if data is not None:
        payload["data"] = data
    payload.update(extra)
    return JSONResponse(payload, status_code=status_code)


def _json_err(message: str, code: int = 400) -> JSONResponse:
    return JSONResponse({"ok": False, "error": message}, status_code=code)


def _int_param(request: Request, key: str) -> int | None:
    try:
        return int(request.path_params[key])
    except (KeyError, TypeError, ValueError):
        return None


async def _read_json(request: Request) -> dict[str, Any]:
    try:
        body = await request.json()
    except Exception:
        return {}
    return body if isinstance(body, dict) else {}


# ------------------------------------------------------------------- routes
async def index(request: Request) -> Response:
    return HTMLResponse(settings.template_dir.joinpath("index.html").read_text(encoding="utf-8"))


async def health(request: Request) -> Response:
    return _json_ok({
        "backend": compat.BACKEND,
        "python": sys.version.split()[0],
        "platform": f"{platform.system()} {platform.machine()}",
        "uptime_sec": round(time.time() - START_TS, 1),
        "time": datetime.now().isoformat(timespec="seconds"),
    })


async def sysinfo(request: Request) -> Response:
    total, used, free = shutil.disk_usage(str(settings.data_dir))
    return _json_ok({
        "backend": compat.BACKEND,
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "machine": platform.machine(),
        "cpu_count": __import__("os").cpu_count(),
        "disk": {
            "total_mb": round(total / 1048576, 1),
            "used_mb": round(used / 1048576, 1),
            "free_mb": round(free / 1048576, 1),
        },
        "data_dir": str(settings.data_dir),
        "uptime_sec": round(time.time() - START_TS, 1),
    })


# ---- notes ---------------------------------------------------------------
async def notes_list(request: Request) -> Response:
    if (r := _guard(request)) is not None:
        return r
    return _json_ok(store.list_notes())


async def notes_create(request: Request) -> Response:
    if (r := _guard(request)) is not None:
        return r
    body = await _read_json(request)
    title = str(body.get("title", "")).strip()
    if not title:
        return _json_err("title 不能为空")
    return _json_ok(store.create_note(title, str(body.get("body", ""))), status_code=201)


async def notes_update(request: Request) -> Response:
    if (r := _guard(request)) is not None:
        return r
    note_id = _int_param(request, "note_id")
    if note_id is None:
        return _json_err("笔记 id 非法")
    body = await _read_json(request)
    title = body.get("title")
    text = body.get("body")
    note = store.update_note(
        note_id,
        None if title is None else str(title),
        None if text is None else str(text),
    )
    if note is None:
        return _json_err("笔记不存在", 404)
    return _json_ok(note)


async def notes_delete(request: Request) -> Response:
    if (r := _guard(request)) is not None:
        return r
    note_id = _int_param(request, "note_id")
    if note_id is None:
        return _json_err("笔记 id 非法")
    if not store.delete_note(note_id):
        return _json_err("笔记不存在", 404)
    return _json_ok({"deleted": note_id})


# ---- uploads -------------------------------------------------------------
async def uploads_list(request: Request) -> Response:
    if (r := _guard(request)) is not None:
        return r
    return _json_ok(store.list_uploads(settings.upload_dir))


async def uploads_post(request: Request) -> Response:
    if (r := _guard(request)) is not None:
        return r
    if request.headers.get("content-length") and int(request.headers["content-length"]) > settings.max_upload_bytes:
        return _json_err(f"文件超过 {settings.max_upload_mb} MB 上限", 413)
    try:
        form = await request.form()
    except Exception as exc:  # python-multipart 缺失时会走到这里
        return _json_err(f"表单解析失败（是否缺少 python-multipart？）：{exc}", 500)

    saved = []
    for _, value in form.multi_items():
        filename = getattr(value, "filename", None)
        if not filename:
            continue
        data = await value.read()
        if len(data) > settings.max_upload_bytes:
            return _json_err(f"{filename} 超过 {settings.max_upload_mb} MB 上限", 413)
        saved.append(store.save_upload(settings.upload_dir, filename, data))
    if not saved:
        return _json_err("没有收到文件")
    return _json_ok(saved, status_code=201)


async def uploads_delete(request: Request) -> Response:
    if (r := _guard(request)) is not None:
        return r
    name = request.path_params["name"]
    if not store.delete_upload(settings.upload_dir, name):
        return _json_err("文件不存在", 404)
    return _json_ok({"deleted": name})


async def uploads_download(request: Request) -> Response:
    name = store.safe_name(request.path_params["name"])
    target = settings.upload_dir / name
    if not target.is_file():
        return _json_err("文件不存在", 404)
    return compat.FileResponse(target, filename=name)


ROUTES = [
    compat.Route("/", index),
    compat.Route("/api/health", health),
    compat.Route("/api/sysinfo", sysinfo),
    compat.Route("/api/notes", notes_list, methods=["GET"]),
    compat.Route("/api/notes", notes_create, methods=["POST"]),
    compat.Route("/api/notes/{note_id}", notes_update, methods=["PUT"]),
    compat.Route("/api/notes/{note_id}", notes_delete, methods=["DELETE"]),
    compat.Route("/api/uploads", uploads_list, methods=["GET"]),
    compat.Route("/api/uploads", uploads_post, methods=["POST"]),
    compat.Route("/api/uploads/{name}", uploads_delete, methods=["DELETE"]),
    compat.Route("/api/uploads/{name}/download", uploads_download, methods=["GET"]),
]
