"""SQLite 存储层。只用标准库，Termux 上零依赖。"""
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterable

SCHEMA = """
CREATE TABLE IF NOT EXISTS notes (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    title      TEXT NOT NULL,
    body       TEXT NOT NULL DEFAULT '',
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_notes_updated ON notes(updated_at DESC);

CREATE TABLE IF NOT EXISTS providers (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT NOT NULL,
    kind       TEXT NOT NULL,
    base_url   TEXT NOT NULL DEFAULT '',
    api_key    TEXT NOT NULL DEFAULT '',
    model      TEXT NOT NULL DEFAULT '',
    created_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS images (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    prompt      TEXT NOT NULL,
    provider    TEXT NOT NULL DEFAULT '',
    model       TEXT NOT NULL DEFAULT '',
    size        TEXT NOT NULL DEFAULT '',
    filename    TEXT NOT NULL,
    error       TEXT NOT NULL DEFAULT '',
    created_at  REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_images_created ON images(created_at DESC);
"""


class Store:
    def __init__(self, db_path: Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._conn() as c:
            c.executescript(SCHEMA)

    @contextmanager
    def _conn(self):
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("PRAGMA journal_mode=WAL")
            yield conn
            conn.commit()
        finally:
            conn.close()

    # ---- notes -------------------------------------------------------
    def list_notes(self) -> list[dict[str, Any]]:
        with self._conn() as c:
            rows = c.execute(
                "SELECT id, title, body, created_at, updated_at "
                "FROM notes ORDER BY updated_at DESC"
            ).fetchall()
        return [dict(r) for r in rows]

    def get_note(self, note_id: int) -> dict[str, Any] | None:
        with self._conn() as c:
            row = c.execute("SELECT * FROM notes WHERE id = ?", (note_id,)).fetchone()
        return dict(row) if row else None

    def create_note(self, title: str, body: str = "") -> dict[str, Any]:
        now = time.time()
        with self._conn() as c:
            cur = c.execute(
                "INSERT INTO notes (title, body, created_at, updated_at) VALUES (?, ?, ?, ?)",
                (title, body, now, now),
            )
            note_id = cur.lastrowid
        return self.get_note(int(note_id))  # type: ignore[arg-type]

    def update_note(self, note_id: int, title: str | None, body: str | None) -> dict[str, Any] | None:
        current = self.get_note(note_id)
        if current is None:
            return None
        title = current["title"] if title is None else title
        body = current["body"] if body is None else body
        with self._conn() as c:
            c.execute(
                "UPDATE notes SET title = ?, body = ?, updated_at = ? WHERE id = ?",
                (title, body, time.time(), note_id),
            )
        return self.get_note(note_id)

    def delete_note(self, note_id: int) -> bool:
        with self._conn() as c:
            cur = c.execute("DELETE FROM notes WHERE id = ?", (note_id,))
        return cur.rowcount > 0

    # ---- uploads (文件落盘，元数据走文件系统) --------------------------
    @staticmethod
    def safe_name(name: str) -> str:
        keep = "-_.() "
        cleaned = "".join(ch for ch in name if ch.isalnum() or ch in keep).strip()
        return cleaned or "unnamed"

    def list_uploads(self, upload_dir: Path) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for p in sorted(upload_dir.glob("*"), key=lambda x: x.stat().st_mtime, reverse=True):
            if p.is_file():
                st = p.stat()
                items.append({"name": p.name, "size": st.st_size, "mtime": st.st_mtime})
        return items

    def save_upload(self, upload_dir: Path, filename: str, data: bytes) -> dict[str, Any]:
        upload_dir.mkdir(parents=True, exist_ok=True)
        name = self.safe_name(filename)
        target = upload_dir / name
        if target.exists():
            stem, suffix = target.stem, target.suffix
            i = 1
            while target.exists():
                target = upload_dir / f"{stem}({i}){suffix}"
                i += 1
        target.write_bytes(data)
        return {"name": target.name, "size": len(data)}

    def delete_upload(self, upload_dir: Path, name: str) -> bool:
        target = upload_dir / self.safe_name(name)
        if target.is_file():
            target.unlink()
            return True
        return False

    # ---- image providers --------------------------------------------
    def list_providers(self, mask_key: bool = True) -> list[dict[str, Any]]:
        with self._conn() as c:
            rows = c.execute("SELECT * FROM providers ORDER BY id").fetchall()
        out = []
        for r in rows:
            d = dict(r)
            if mask_key and d.get("api_key"):
                k = d["api_key"]
                d["api_key"] = f"****{k[-4:]}" if len(k) > 8 else "****"
            out.append(d)
        return out

    def get_provider(self, provider_id: int) -> dict[str, Any] | None:
        with self._conn() as c:
            row = c.execute("SELECT * FROM providers WHERE id = ?", (provider_id,)).fetchone()
        return dict(row) if row else None

    def create_provider(self, name: str, kind: str, base_url: str, api_key: str, model: str) -> dict[str, Any]:
        with self._conn() as c:
            cur = c.execute(
                "INSERT INTO providers (name, kind, base_url, api_key, model, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (name, kind, base_url, api_key, model, time.time()),
            )
            pid = cur.lastrowid
        return self.get_provider(int(pid))  # type: ignore[arg-type]

    def update_provider(self, provider_id: int, fields: dict[str, Any]) -> dict[str, Any] | None:
        cur = self.get_provider(provider_id)
        if cur is None:
            return None
        allowed = ("name", "kind", "base_url", "api_key", "model")
        merged = {k: (fields[k] if k in fields else cur[k]) for k in allowed}
        # 前端回传掩码时不覆盖真实 key
        if str(merged["api_key"]).startswith("****"):
            merged["api_key"] = cur["api_key"]
        with self._conn() as c:
            c.execute(
                "UPDATE providers SET name=?, kind=?, base_url=?, api_key=?, model=? WHERE id=?",
                (merged["name"], merged["kind"], merged["base_url"],
                 merged["api_key"], merged["model"], provider_id),
            )
        return self.get_provider(provider_id)

    def delete_provider(self, provider_id: int) -> bool:
        with self._conn() as c:
            cur = c.execute("DELETE FROM providers WHERE id = ?", (provider_id,))
        return cur.rowcount > 0

    # ---- generated images -------------------------------------------
    def add_image(self, prompt: str, provider: str, model: str, size: str,
                  filename: str, error: str = "") -> dict[str, Any]:
        with self._conn() as c:
            cur = c.execute(
                "INSERT INTO images (prompt, provider, model, size, filename, error, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (prompt, provider, model, size, filename, error, time.time()),
            )
            iid = cur.lastrowid
        with self._conn() as c:
            row = c.execute("SELECT * FROM images WHERE id = ?", (iid,)).fetchone()
        return dict(row)

    def list_images(self, limit: int = 60) -> list[dict[str, Any]]:
        with self._conn() as c:
            rows = c.execute(
                "SELECT * FROM images ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(r) for r in rows]

    def delete_image(self, image_id: int) -> str | None:
        with self._conn() as c:
            row = c.execute("SELECT filename FROM images WHERE id = ?", (image_id,)).fetchone()
            if not row:
                return None
            c.execute("DELETE FROM images WHERE id = ?", (image_id,))
        return row["filename"]


def rows_to_json(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    return [dict(r) for r in rows]
