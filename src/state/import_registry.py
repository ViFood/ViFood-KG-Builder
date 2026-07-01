import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


class ImportRegistry:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.payload = self._load()

    def is_imported(self, entity_type: str, entity_id: str, source_hash: str) -> bool:
        entry = self.payload["imported"].get(self._key(entity_type, entity_id))
        return bool(entry and entry.get("source_hash") == source_hash)

    def mark_imported(self, items: list[dict[str, Any]], output_file: str | Path | None = None) -> None:
        imported_at = datetime.now(UTC).isoformat()
        for item in items:
            entity_type = str(item.get("entity_type") or "")
            entity_id = str(item.get("entity_id") or "")
            if not entity_type or not entity_id:
                continue
            sections = item.get("wiki_sections") or []
            profile = item.get("wiki_profile") or {}
            self.payload["imported"][self._key(entity_type, entity_id)] = {
                "entity_type": entity_type,
                "entity_id": entity_id,
                "source_hash": item.get("source_hash"),
                "wiki_profile_id": profile.get("id"),
                "section_count": len(sections),
                "section_types": [section.get("section_type") for section in sections],
                "imported_at": imported_at,
                "output_file": str(output_file) if output_file else None,
            }
        self.payload["metadata"]["updated_at"] = imported_at
        self.payload["metadata"]["imported_count"] = len(self.payload["imported"])
        self.save()

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as f:
            json.dump(self.payload, f, ensure_ascii=False, indent=2)
            f.write("\n")

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            now = datetime.now(UTC).isoformat()
            return {
                "metadata": {
                    "project": "ViFood-KG-Builder",
                    "created_at": now,
                    "updated_at": now,
                    "imported_count": 0,
                },
                "imported": {},
            }
        with self.path.open("r", encoding="utf-8") as f:
            payload = json.load(f)
        if not isinstance(payload, dict):
            raise ValueError(f"Import registry must be a JSON object: {self.path}")
        payload.setdefault("metadata", {})
        payload.setdefault("imported", {})
        if not isinstance(payload["imported"], dict):
            raise ValueError(f"Import registry `imported` must be an object: {self.path}")
        return payload

    @staticmethod
    def _key(entity_type: str, entity_id: str) -> str:
        return f"{entity_type}:{entity_id}"
