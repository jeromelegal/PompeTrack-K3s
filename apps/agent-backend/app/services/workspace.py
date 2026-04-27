from __future__ import annotations

from pathlib import Path

from app.core.config import Settings


class WorkspaceService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def _resolve(self, relative_path: str) -> Path:
        root = self.settings.workspace_root.resolve()
        path = (root / relative_path).resolve()
        if root not in path.parents and path != root:
            raise ValueError("path escapes workspace root")
        return path

    def list_files(self, relative_path: str = ".") -> list[dict]:
        path = self._resolve(relative_path)
        if not path.exists():
            return []
        items: list[dict] = []
        if path.is_file():
            return [{"path": str(path.relative_to(self.settings.workspace_root)), "type": "file"}]
        for item in sorted(path.rglob("*")):
            if len(items) >= self.settings.max_workspace_results:
                break
            item_type = "dir" if item.is_dir() else "file"
            items.append({"path": str(item.relative_to(self.settings.workspace_root)), "type": item_type})
        return items

    def read_file(self, relative_path: str) -> dict:
        path = self._resolve(relative_path)
        if not path.exists() or not path.is_file():
            raise ValueError("file not found")
        raw = path.read_text(encoding="utf-8", errors="ignore")
        return {
            "path": str(path.relative_to(self.settings.workspace_root)),
            "content": raw[: self.settings.max_scrape_chars],
        }
