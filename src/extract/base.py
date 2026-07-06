from typing import Any

from src.db.neo4j_connection import SourceNeo4jConnection


class BaseExtractor:
    list_query: str
    by_id_query: str

    def __init__(self, connection: SourceNeo4jConnection) -> None:
        self.connection = connection

    def get_all(self, limit: int | None = None) -> list[dict[str, Any]]:
        rows = self.connection.read(self.list_query, {"limit": limit})
        return [self._normalize(row) for row in rows]

    def get_by_id(self, entity_id: str) -> dict[str, Any] | None:
        rows = self.connection.read(self.by_id_query, {"entity_id": entity_id})
        if not rows:
            return None
        return self._normalize(rows[0])

    @staticmethod
    def _normalize(row: dict[str, Any]) -> dict[str, Any]:
        return {
            "entity": row.get("entity") or {},
            "relationships": row.get("relationships") or {},
        }


def cypher_label(label: str) -> str:
    if not label or not label.replace("_", "").isalnum() or label[0].isdigit():
        raise ValueError(f"Invalid Neo4j label configured: {label!r}")
    return label
