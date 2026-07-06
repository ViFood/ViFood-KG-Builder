import json
from pathlib import Path
from typing import Any

from src.db.neo4j_connection import TargetNeo4jConnection
from src.validate.wiki_validator import WikiValidator


IMPORT_QUERY = """
UNWIND $items AS item
CALL {
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
    profile.reviewed_at = item.wiki_profile.reviewed_at,
    profile.source_hash = item.source_hash
MERGE (entity)-[:HAS_WIKI_PROFILE]->(profile)
WITH profile, item
OPTIONAL MATCH (profile)-[oldRel:HAS_SECTION]->(:WikiSection)
DELETE oldRel
WITH profile, item
UNWIND item.wiki_sections AS sectionData
MERGE (section:WikiSection {id: sectionData.id})
SET section.title = sectionData.title,
    section.content = sectionData.content,
    section.section_type = sectionData.section_type,
    section.status = sectionData.status,
    section.order = sectionData.order,
    section.source_hash = item.source_hash,
    section.generated_by = coalesce(sectionData.generated_by, 'template')
MERGE (profile)-[:HAS_SECTION {order: sectionData.order}]->(section)
"""

ALLOWED_SECTION_TYPES = {
    "overview",
    "classification_and_role",
    "common_foods",
    "health_note",
    "source_and_regulation",
}


CACHED_SECTIONS_QUERY = """
MATCH (profile:WikiProfile {id: $profile_id})
WHERE profile.source_hash = $source_hash
MATCH (profile)-[rel:HAS_SECTION]->(section:WikiSection)
RETURN profile {
  .id,
  .title,
  .subtitle,
  .summary,
  .entity_type,
  .language,
  .audience,
  .status,
  .reviewed_at,
  .source_hash
} AS wiki_profile,
collect(section {
  .id,
  .title,
  .content,
  .section_type,
  order: rel.order,
  .status,
  .source_hash,
  .generated_by
}) AS wiki_sections
"""


class Neo4jLoader:
    def __init__(self, connection: TargetNeo4jConnection) -> None:
        self.connection = connection
        self.validator = WikiValidator()

    def import_file(self, path: str | Path) -> dict[str, Any]:
        self.validator.assert_valid_file(path)
        with Path(path).open("r", encoding="utf-8") as f:
            payload = json.load(f)
        return self.import_payload(payload)

    def import_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        errors = self.validator.validate_payload(payload)
        if errors:
            raise ValueError("\n".join(errors))
        items = payload["items"]
        self.connection.write(IMPORT_QUERY, {"items": items})
        return {"items_imported": len(items)}

    def get_cached_wiki(self, profile_id: str, source_hash: str) -> dict[str, Any] | None:
        rows = self.connection.read(
            CACHED_SECTIONS_QUERY,
            {"profile_id": profile_id, "source_hash": source_hash},
        )
        if not rows:
            return None
        row = rows[0]
        sections = sorted(row.get("wiki_sections") or [], key=lambda item: item.get("order") or 0)
        if not sections:
            return None
        if any(section.get("section_type") not in ALLOWED_SECTION_TYPES for section in sections):
            return None
        return {"wiki_profile": row["wiki_profile"], "wiki_sections": sections}
