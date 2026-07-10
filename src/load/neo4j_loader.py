import json
from pathlib import Path
from typing import Any

from src.db.neo4j_connection import TargetNeo4jConnection


ADDITIVE_IMPORT_QUERY = """
UNWIND $items AS item
MERGE (entity:Additive {id: item.entity.id})
SET entity += item.entity
WITH entity, item
FOREACH (nodeData IN [x IN coalesce(item.relationships.functions, []) WHERE x.id IS NOT NULL] |
  MERGE (related:FunctionalClass {id: nodeData.id})
  SET related += nodeData
  MERGE (entity)-[:HAS_FUNCTION]->(related)
)
FOREACH (nodeData IN [x IN coalesce(item.relationships.permitted_in, []) WHERE x.id IS NOT NULL] |
  MERGE (related:FoodCategory {id: nodeData.id})
  SET related += nodeData
  MERGE (entity)-[:PERMITTED_IN]->(related)
)
FOREACH (nodeData IN [x IN coalesce(item.relationships.sources, []) WHERE x.id IS NOT NULL] |
  MERGE (related:Source {id: nodeData.id})
  SET related += nodeData
  MERGE (entity)-[:SUPPORTED_BY]->(related)
)
FOREACH (nodeData IN [x IN coalesce(item.relationships.aliases, []) WHERE x.id IS NOT NULL] |
  MERGE (related:Alias {id: nodeData.id})
  SET related += nodeData
  MERGE (related)-[:REFERS_TO]->(entity)
)
FOREACH (nodeData IN [x IN coalesce(item.relationships.regulations, []) WHERE x.id IS NOT NULL] |
  MERGE (related:Regulation {id: nodeData.id})
  SET related += nodeData
  MERGE (related)-[:GOVERNS]->(entity)
)
"""


NUTRIENT_IMPORT_QUERY = """
UNWIND $items AS item
MERGE (entity:Nutrient {id: item.entity.id})
SET entity += item.entity
WITH entity, item
FOREACH (nodeData IN [x IN coalesce(item.relationships.sources, []) WHERE x.id IS NOT NULL] |
  MERGE (related:Source {id: nodeData.id})
  SET related += nodeData
  MERGE (entity)-[:SUPPORTED_BY]->(related)
)
FOREACH (nodeData IN [x IN coalesce(item.relationships.health_claims, []) WHERE x.id IS NOT NULL] |
  MERGE (related:HealthClaim {id: nodeData.id})
  SET related += nodeData
  MERGE (related)-[:SUBJECT_OF]->(entity)
)
FOREACH (nodeData IN [x IN coalesce(item.relationships.ingredients, []) WHERE x.id IS NOT NULL] |
  MERGE (related:Ingredient {id: nodeData.id})
  SET related += nodeData
  MERGE (related)-[:HAS_NUTRIENT]->(entity)
)
FOREACH (nodeData IN [x IN coalesce(item.relationships.aliases, []) WHERE x.id IS NOT NULL] |
  MERGE (related:Alias {id: nodeData.id})
  SET related += nodeData
  MERGE (related)-[:REFERS_TO]->(entity)
)
"""


ENTITY_TYPES = ("additive", "nutrient")


class Neo4jLoader:
    def __init__(self, connection: TargetNeo4jConnection) -> None:
        self.connection = connection

    def import_file(self, path: str | Path) -> dict[str, Any]:
        with Path(path).open("r", encoding="utf-8") as f:
            payload = json.load(f)
        return self.import_payload(payload)

    def import_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.validate_payload(payload)
        items = payload["items"]
        additive_items = [item for item in items if item["entity_type"] == "additive"]
        nutrient_items = [item for item in items if item["entity_type"] == "nutrient"]

        if additive_items:
            self.connection.write(ADDITIVE_IMPORT_QUERY, {"items": additive_items})
        if nutrient_items:
            self.connection.write(NUTRIENT_IMPORT_QUERY, {"items": nutrient_items})

        return {
            "items_imported": len(items),
            "additives_imported": len(additive_items),
            "nutrients_imported": len(nutrient_items),
        }

    @staticmethod
    def validate_payload(payload: Any) -> None:
        if not isinstance(payload, dict) or not isinstance(payload.get("items"), list):
            raise ValueError("Root JSON must be an object with an items list.")

        for index, item in enumerate(payload["items"], start=1):
            if not isinstance(item, dict):
                raise ValueError(f"Item #{index} must be an object.")
            entity_type = item.get("entity_type")
            if entity_type not in ENTITY_TYPES:
                raise ValueError(f"Item #{index}: entity_type must be additive or nutrient.")
            entity = item.get("entity")
            relationships = item.get("relationships")
            if not isinstance(entity, dict):
                raise ValueError(f"Item #{index}: entity must be an object.")
            if not entity.get("id"):
                raise ValueError(f"Item #{index}: entity.id is required.")
            if not isinstance(relationships, dict):
                raise ValueError(f"Item #{index}: relationships must be an object.")
