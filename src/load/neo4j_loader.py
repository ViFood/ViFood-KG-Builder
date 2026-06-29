import json
from pathlib import Path
from typing import Any

from src.db.neo4j_connection import TargetNeo4jConnection
from src.validate.wiki_validator import WikiValidator


IMPORT_QUERY = """
UNWIND $items AS item
CALL {
  WITH item
  WITH item WHERE item.entity_type = 'ingredient'
  MERGE (entity:Ingredient {id: item.entity_id})
  SET entity += coalesce(item.source_entity, {})
  RETURN entity
  UNION
  WITH item
  WITH item WHERE item.entity_type = 'additive'
  MERGE (entity:Additive {id: item.entity_id})
  SET entity += coalesce(item.source_entity, {})
  RETURN entity
  UNION
  WITH item
  WITH item WHERE item.entity_type = 'nutrient'
  MERGE (entity:Nutrient {id: item.entity_id})
  SET entity += coalesce(item.source_entity, {})
  RETURN entity
}
WITH entity, item
MERGE (profile:WikiProfile {id: item.wiki_profile.id})
SET profile.title = item.wiki_profile.title,
    profile.subtitle = item.wiki_profile.subtitle,
    profile.summary = item.wiki_profile.summary,
    profile.entity_type = item.wiki_profile.entity_type,
    profile.language = item.wiki_profile.language,
    profile.audience = item.wiki_profile.audience,
    profile.status = item.wiki_profile.status,
    profile.reviewed_at = item.wiki_profile.reviewed_at
MERGE (entity)-[:HAS_WIKI_PROFILE]->(profile)
WITH profile, item
UNWIND item.wiki_sections AS sectionData
MERGE (section:WikiSection {id: sectionData.id})
SET section.title = sectionData.title,
    section.content = sectionData.content,
    section.section_type = sectionData.section_type,
    section.status = sectionData.status,
    section.order = sectionData.order
MERGE (profile)-[:HAS_SECTION {order: sectionData.order}]->(section)
"""


class Neo4jLoader:
    def __init__(self, connection: TargetNeo4jConnection) -> None:
        self.connection = connection
        self.validator = WikiValidator()

    def import_file(self, path: str | Path) -> dict[str, Any]:
        self.validator.assert_valid_file(path)
        with Path(path).open("r", encoding="utf-8") as f:
            payload = json.load(f)
        items = payload["items"]
        self.connection.write(IMPORT_QUERY, {"items": items})
        return {"items_imported": len(items)}
