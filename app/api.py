"""HTTP 路由。全部用 Starlette 的 Request/Response，两个后端都能跑。"""
from __future__ import annotations

import platform
import shutil
import sys
import time
import uuid
from datetime import datetime
from typing import Any

from . import compat, providers
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


# ---- image providers -----------------------------------------------------
async def providers_kinds(request: Request) -> Response:
    return _json_ok([{"kind": k, "desc": v} for k, v in providers.KINDS.items()])


async def providers_list(request: Request) -> Response:
    if (r := _guard(request)) is not None:
        return r
    return _json_ok(store.list_providers())


async def providers_create(request: Request) -> Response:
    if (r := _guard(request)) is not None:
        return r
    body = await _read_json(request)
    kind = str(body.get("kind", "")).strip()
    if kind not in providers.KINDS:
        return _json_err(f"未知类型 {kind}，可选：{', '.join(providers.KINDS)}")
    name = str(body.get("name", "")).strip() or kind
    if not str(body.get("api_key", "")).strip():
        return _json_err("api_key 不能为空")
    p = store.create_provider(
        name, kind,
        str(body.get("base_url", "")).strip(),
        str(body.get("api_key", "")).strip(),
        str(body.get("model", "")).strip(),
    )
    return _json_ok(_mask(p), status_code=201)


async def providers_update(request: Request) -> Response:
    if (r := _guard(request)) is not None:
        return r
    pid = _int_param(request, "provider_id")
    if pid is None:
        return _json_err("id 非法")
    fields = await _read_json(request)
    if "kind" in fields and fields["kind"] not in providers.KINDS:
        return _json_err("未知类型")
    p = store.update_provider(pid, fields)
    if p is None:
        return _json_err("配置不存在", 404)
    return _json_ok(_mask(p))


async def providers_delete(request: Request) -> Response:
    if (r := _guard(request)) is not None:
        return r
    pid = _int_param(request, "provider_id")
    if pid is None:
        return _json_err("id 非法")
    if not store.delete_provider(pid):
        return _json_err("配置不存在", 404)
    return _json_ok({"deleted": pid})


def _mask(p: dict | None) -> dict | None:
    if p is None:
        return None
    d = dict(p)
    k = d.get("api_key") or ""
    d["api_key"] = f"****{k[-4:]}" if len(k) > 8 else ("****" if k else "")
    return d


# ---- image generation ----------------------------------------------------
async def images_list(request: Request) -> Response:
    if (r := _guard(request)) is not None:
        return r
    return _json_ok(store.list_images())


async def images_generate(request: Request) -> Response:
    if (r := _guard(request)) is not None:
        return r
    body = await _read_json(request)
    prompt = str(body.get("prompt", "")).strip()
    if not prompt:
        return _json_err("prompt 不能为空")

    pid = body.get("provider_id")
    if not pid:
        return _json_err("请先选择一个 provider 配置")
    p = store.get_provider(int(pid))
    if p is None:
        return _json_err("provider 配置不存在", 404)

    size = str(body.get("size", "1024x1024")).strip() or "1024x1024"
    n = int(body.get("n", 1) or 1)
    label = f"{p['name']}/{p['model'] or '-'}"

    try:
        blobs = await providers.generate(p, prompt, size, n)
    except providers.ProviderError as exc:
        store.add_image(prompt, p["name"], p["model"], size, "", str(exc))
        return _json_err(f"生成失败：{exc}", 502)
    except Exception as exc:  # 兜底，别让整个服务挂掉
        store.add_image(prompt, p["name"], p["model"], size, "", str(exc))
        return _json_err(f"生成异常：{exc}", 500)

    saved = []
    for blob in blobs:
        name = f"{datetime.now():%Y%m%d-%H%M%S}-{uuid.uuid4().hex[:6]}{_sniff_ext(blob)}"
        settings.image_dir.mkdir(parents=True, exist_ok=True)
        (settings.image_dir / name).write_bytes(blob)
        saved.append(store.add_image(prompt, p["name"], p["model"], size, name))
    return _json_ok(saved, status_code=201, provider=label)


def _sniff_ext(blob: bytes) -> str:
    if blob[:8] == b"\x89PNG\r\n\x1a\n":
        return ".png"
    if blob[:3] == b"\xff\xd8\xff":
        return ".jpg"
    if blob[:4] == b"RIFF" and blob[8:12] == b"WEBP":
        return ".webp"
    return ".png"


async def images_delete(request: Request) -> Response:
    if (r := _guard(request)) is not None:
        return r
    iid = _int_param(request, "image_id")
    if iid is None:
        return _json_err("id 非法")
    filename = store.delete_image(iid)
    if filename is None:
        return _json_err("记录不存在", 404)
    if filename:
        target = settings.image_dir / filename
        if target.is_file():
            target.unlink()
    return _json_ok({"deleted": iid})


async def images_file(request: Request) -> Response:
    name = str(request.path_params["name"])
    target = settings.image_dir / name
    if not target.is_file():
        return _json_err("图片不存在", 404)
    return compat.FileResponse(target)


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
    # 图片生成
    compat.Route("/api/providers/kinds", providers_kinds),
    compat.Route("/api/providers", providers_list, methods=["GET"]),
    compat.Route("/api/providers", providers_create, methods=["POST"]),
    compat.Route("/api/providers/{provider_id}", providers_update, methods=["PUT"]),
    compat.Route("/api/providers/{provider_id}", providers_delete, methods=["DELETE"]),
    compat.Route("/api/images", images_list, methods=["GET"]),
    compat.Route("/api/images", images_generate, methods=["POST"]),
    compat.Route("/api/images/{image_id}", images_delete, methods=["DELETE"]),
    compat.Route("/api/images/file/{name}", images_file, methods=["GET"]),
]
