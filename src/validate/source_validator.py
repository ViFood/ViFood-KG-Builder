from typing import Any


class SourceValidator:
    def validate(self, item: dict[str, Any]) -> list[str]:
        entity_id = item.get("entity_id", "<missing entity_id>")
        evidence = item.get("evidence") or {}
        related = item.get("related") or {}
        source_entity = item.get("source_entity") or {}
        has_source = bool(evidence.get("source_id") or evidence.get("source") or evidence.get("sources"))
        has_related_source = bool(related.get("sources"))
        has_source_payload = bool(source_entity or related or evidence)
        if not has_source and not has_related_source and not has_source_payload:
            return [f"{entity_id}: entity must include data extracted from source Neo4j."]
        return []
