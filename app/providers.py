"""图片生成 provider 适配层。

四种类型覆盖绝大多数服务商：
  openai_images  —— OpenAI /v1/images/generations（OpenAI、硅基流动、多数中转站）
  openai_chat    —— OpenAI 兼容 chat 接口，图片从 message 里回来（Gemini 中转、多模态模型）
  gemini         —— Google Gemini 原生 generateContent
  dashscope      —— 阿里百炼万相（异步任务 + 轮询）

只用标准库 urllib（丢进线程池跑），不引入 httpx/aiohttp，保持 Termux 零编译。
"""
from __future__ import annotations

import asyncio
import base64
import json
import time
import urllib.error
import urllib.request
from typing import Any

KINDS = {
    "openai_images": "OpenAI /images/generations（OpenAI、硅基流动、多数中转站）",
    "openai_chat": "OpenAI 兼容 chat 接口返回图片（Gemini 中转、多模态模型）",
    "gemini": "Google Gemini 原生接口",
    "dashscope": "阿里百炼万相（异步任务）",
}

TIMEOUT = 180


class ProviderError(Exception):
    pass


# ---------------------------------------------------------------- http helpers
def _post_json(url: str, payload: dict, headers: dict[str, str]) -> dict:
    data = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    for k, v in headers.items():
        req.add_header(k, v)
    return _do(req)


def _get_json(url: str, headers: dict[str, str]) -> dict:
    req = urllib.request.Request(url, method="GET")
    for k, v in headers.items():
        req.add_header(k, v)
    return _do(req)


def _do(req: urllib.request.Request) -> dict:
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            body = resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:600]
        raise ProviderError(f"HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise ProviderError(f"网络错误: {exc.reason}") from exc
    try:
        parsed = json.loads(body)
    except json.JSONDecodeError:
        raise ProviderError(f"返回的不是 JSON: {body[:300]}") from None
    if not isinstance(parsed, dict):
        raise ProviderError("返回结构异常")
    return parsed


def _download(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "termux-webui/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return resp.read()
    except Exception as exc:
        raise ProviderError(f"下载生成的图片失败: {exc}") from exc


def _from_b64(s: str) -> bytes:
    if "," in s and s.strip().startswith("data:"):
        s = s.split(",", 1)[1]
    try:
        return base64.b64decode(s)
    except Exception as exc:
        raise ProviderError(f"base64 解码失败: {exc}") from exc


def _norm_base(base: str) -> str:
    base = (base or "").strip().rstrip("/")
    if not base:
        raise ProviderError("base_url 未填写")
    if not base.startswith(("http://", "https://")):
        base = "https://" + base
    return base


# ------------------------------------------------------------------- adapters
def _openai_images(p: dict, prompt: str, size: str, n: int) -> list[bytes]:
    base = _norm_base(p["base_url"])
    url = base + "/images/generations"
    payload: dict[str, Any] = {
        "model": p["model"] or "gpt-image-1",
        "prompt": prompt,
        "n": n,
        "size": size,
    }
    headers = {"Authorization": f"Bearer {p['api_key']}"}
    try:
        resp = _post_json(url, {**payload, "response_format": "b64_json"}, headers)
    except ProviderError as exc:
        # 部分服务商不认 response_format，去掉重试一次
        if "response_format" not in str(exc) and "400" not in str(exc):
            raise
        resp = _post_json(url, payload, headers)

    items = resp.get("data") or []
    if not items:
        raise ProviderError(f"返回里没有 data: {json.dumps(resp)[:300]}")
    out: list[bytes] = []
    for it in items:
        if it.get("b64_json"):
            out.append(_from_b64(it["b64_json"]))
        elif it.get("url"):
            out.append(_download(it["url"]))
    if not out:
        raise ProviderError("返回里既没有 b64_json 也没有 url")
    return out


def _openai_chat(p: dict, prompt: str, size: str, n: int) -> list[bytes]:
    base = _norm_base(p["base_url"])
    url = base + "/chat/completions"
    payload = {
        "model": p["model"],
        "messages": [{"role": "user", "content": prompt}],
        "modalities": ["image", "text"],
    }
    headers = {"Authorization": f"Bearer {p['api_key']}"}
    resp = _post_json(url, payload, headers)

    choices = resp.get("choices") or []
    if not choices:
        raise ProviderError(f"返回里没有 choices: {json.dumps(resp)[:300]}")
    msg = choices[0].get("message") or {}

    out: list[bytes] = []
    # 形态 A：message.images[].image_url.url
    for it in msg.get("images") or []:
        u = it.get("image_url", {}).get("url") if isinstance(it.get("image_url"), dict) else it.get("image_url")
        if u:
            out.append(_from_b64(u) if u.startswith("data:") or len(u) > 2000 else _download(u))
    # 形态 B：content 是数组，含 image_url part
    content = msg.get("content")
    if isinstance(content, list):
        for part in content:
            if isinstance(part, dict) and part.get("type") in ("image_url", "output_image"):
                u = part.get("image_url")
                if isinstance(u, dict):
                    u = u.get("url")
                if u:
                    out.append(_from_b64(u) if u.startswith("data:") else _download(u))
    if not out:
        raise ProviderError("没有从返回里找到图片，可能是模型不支持出图")
    return out


def _gemini(p: dict, prompt: str, size: str, n: int) -> list[bytes]:
    base = _norm_base(p["base_url"] or "https://generativelanguage.googleapis.com/v1beta")
    model = p["model"] or "gemini-2.5-flash-image"
    url = f"{base}/models/{model}:generateContent?key={p['api_key']}"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"responseModalities": ["TEXT", "IMAGE"]},
    }
    resp = _post_json(url, payload, {})

    out: list[bytes] = []
    for cand in resp.get("candidates") or []:
        for part in (cand.get("content") or {}).get("parts") or []:
            inline = part.get("inlineData") or part.get("inline_data")
            if inline and inline.get("data"):
                out.append(_from_b64(inline["data"]))
    if not out:
        raise ProviderError(f"没有找到 inlineData 图片: {json.dumps(resp)[:300]}")
    return out


def _dashscope(p: dict, prompt: str, size: str, n: int) -> list[bytes]:
    base = _norm_base(p["base_url"] or "https://dashscope.aliyuncs.com/api/v1")
    headers = {
        "Authorization": f"Bearer {p['api_key']}",
        "X-DashScope-Async": "enable",
    }
    payload = {
        "model": p["model"] or "wanx2.1-t2i-turbo",
        "input": {"prompt": prompt},
        "parameters": {"size": size.replace("x", "*"), "n": n},
    }
    created = _post_json(base + "/services/aigc/text2image/image-synthesis", payload, headers)
    task_id = (created.get("output") or {}).get("task_id")
    if not task_id:
        raise ProviderError(f"没拿到 task_id: {json.dumps(created)[:300]}")

    deadline = time.time() + TIMEOUT
    while time.time() < deadline:
        status = _get_json(f"{base}/tasks/{task_id}", {"Authorization": f"Bearer {p['api_key']}"})
        out_obj = status.get("output") or {}
        state = out_obj.get("task_status")
        if state == "SUCCEEDED":
            results = out_obj.get("results") or []
            if not results:
                raise ProviderError("任务成功但没有结果")
            return [_download(r["url"]) for r in results if r.get("url")]
        if state in ("FAILED", "CANCELED", "UNKNOWN"):
            raise ProviderError(f"任务失败: {out_obj.get('message') or state}")
        time.sleep(3)
    raise ProviderError("轮询超时")


_ADAPTERS = {
    "openai_images": _openai_images,
    "openai_chat": _openai_chat,
    "gemini": _gemini,
    "dashscope": _dashscope,
}


# ------------------------------------------------------------------ public API
def generate_sync(provider: dict, prompt: str, size: str = "1024x1024", n: int = 1) -> list[bytes]:
    kind = provider.get("kind", "")
    fn = _ADAPTERS.get(kind)
    if fn is None:
        raise ProviderError(f"不支持的 provider 类型: {kind}")
    return fn(provider, prompt, size, max(1, min(int(n or 1), 4)))


async def generate(provider: dict, prompt: str, size: str = "1024x1024", n: int = 1) -> list[bytes]:
    """放进线程池跑，避免阻塞事件循环（urllib 是同步的）。"""
    return await asyncio.to_thread(generate_sync, provider, prompt, size, n)
