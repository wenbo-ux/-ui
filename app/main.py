"""ASGI 应用装配。uvicorn 目标：app.main:app"""
from __future__ import annotations

import socket
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import compat  # noqa: E402
from app.api import ROUTES  # noqa: E402
from app.config import settings  # noqa: E402

app = compat.build_app(
    ROUTES,
    title=settings.app_name,
    version="1.0.0",
    description="Termux 友好的一体化 WebUI 脚手架（FastAPI / Starlette 双后端）",
)

try:
    from starlette.staticfiles import StaticFiles

    app.mount("/static", StaticFiles(directory=str(settings.static_dir)), name="static")
except Exception as exc:  # pragma: no cover
    print(f"[warn] 静态目录挂载失败：{exc}")


def lan_ip() -> str:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"
    finally:
        s.close()


def main() -> None:
    settings.ensure_dirs()
    import uvicorn

    ip = lan_ip()
    print("=" * 52)
    print(f"  {settings.app_name}")
    print(f"  后端     : {compat.BACKEND}")
    print(f"  本机访问 : http://127.0.0.1:{settings.port}")
    print(f"  局域网   : http://{ip}:{settings.port}")
    if compat.BACKEND == "fastapi":
        print(f"  接口文档 : http://{ip}:{settings.port}/docs")
    print(f"  数据目录 : {settings.data_dir}")
    print("=" * 52)
    uvicorn.run(
        "app.main:app" if settings.reload else app,
        host=settings.host,
        port=settings.port,
        reload=settings.reload,
        log_level="info",
    )


if __name__ == "__main__":
    main()
