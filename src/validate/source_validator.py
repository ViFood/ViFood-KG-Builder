from typing import Any


class SourceValidator:
    def validate(self, item: dict[str, Any]) -> list[str]:
        entity_id = item.get("entity_id", "<missing entity_id>")
        evidence = item.get("evidence") or {}
        related = item.get("related") or {}
        has_source = bool(evidence.get("source_id") or evidence.get("source") or evidence.get("sources"))
        has_related_source = bool(related.get("sources"))
        if not has_source and not has_related_source:
            return [f"{entity_id}: entity must have source evidence or related supported_by Source."]
        return []
