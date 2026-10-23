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


def rows_to_json(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    return [dict(r) for r in rows]
