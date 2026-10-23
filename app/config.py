"""集中配置。不依赖 python-dotenv，自己解析 .env。"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def _load_dotenv(path: Path) -> None:
    """极简 .env 解析：KEY=VALUE，忽略 # 注释，已存在的环境变量优先。"""
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        os.environ.setdefault(key, val)


_load_dotenv(BASE_DIR / ".env")


def _flag(name: str, default: str = "0") -> bool:
    return os.getenv(name, default).strip().lower() in ("1", "true", "yes", "on")


class Settings:
    def __init__(self) -> None:
        self.app_name: str = os.getenv("APP_NAME", "Termux WebUI")
        self.host: str = os.getenv("HOST", "0.0.0.0")
        self.port: int = int(os.getenv("PORT", "8000"))
        self.reload: bool = _flag("RELOAD")
        self.data_dir: Path = Path(os.getenv("DATA_DIR", str(BASE_DIR / "data")))
        self.upload_dir: Path = self.data_dir / "uploads"
        self.db_path: Path = self.data_dir / "app.db"
        self.max_upload_mb: int = int(os.getenv("MAX_UPLOAD_MB", "50"))
        # 留空 = 不校验；填了就在 /api 下要求 token（?token= 或 X-Token 头）
        self.token: str = os.getenv("APP_TOKEN", "").strip()
        self.static_dir: Path = BASE_DIR / "app" / "static"
        self.template_dir: Path = BASE_DIR / "app" / "templates"

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024

    def ensure_dirs(self) -> None:
        self.upload_dir.mkdir(parents=True, exist_ok=True)


settings = Settings()
