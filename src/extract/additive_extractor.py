from src.extract.base import BaseExtractor


ADDITIVE_RETURN = """
RETURN additive {
  .*,
  id: coalesce(additive.id, additive.ins, additive.code, additive.name, elementId(additive)),
  labels: labels(additive)
} AS entity,
{
  functions: [x IN collect(DISTINCT CASE WHEN functionalClass IS NULL THEN NULL ELSE functionalClass {.*, id: coalesce(functionalClass.id, functionalClass.code, functionalClass.name, elementId(functionalClass)), labels: labels(functionalClass)} END) WHERE x IS NOT NULL],
  permitted_in: [x IN collect(DISTINCT CASE WHEN foodCategory IS NULL THEN NULL ELSE foodCategory {.*, id: coalesce(foodCategory.id, foodCategory.code, foodCategory.name, elementId(foodCategory)), labels: labels(foodCategory)} END) WHERE x IS NOT NULL],
  sources: [x IN collect(DISTINCT CASE WHEN source IS NULL THEN NULL ELSE source {.*, id: coalesce(source.id, source.code, source.name, elementId(source)), labels: labels(source)} END) WHERE x IS NOT NULL],
  aliases: [x IN collect(DISTINCT CASE WHEN alias IS NULL THEN NULL ELSE alias {.*, id: coalesce(alias.id, alias.code, alias.name, elementId(alias)), labels: labels(alias)} END) WHERE x IS NOT NULL],
  regulations: [x IN collect(DISTINCT CASE WHEN regulation IS NULL THEN NULL ELSE regulation {.*, id: coalesce(regulation.id, regulation.code, regulation.name, elementId(regulation)), labels: labels(regulation)} END) WHERE x IS NOT NULL]
} AS relationships
"""


class AdditiveExtractor(BaseExtractor):
    list_query = f"""
    MATCH (additive:Additive)
    OPTIONAL MATCH (additive)-[:HAS_FUNCTION]->(functionalClass:FunctionalClass)
    OPTIONAL MATCH (additive)-[:PERMITTED_IN]->(foodCategory:FoodCategory)
    OPTIONAL MATCH (additive)-[:SUPPORTED_BY]->(source:Source)
    OPTIONAL MATCH (alias:Alias)-[:REFERS_TO]->(additive)
    OPTIONAL MATCH (regulation:Regulation)-[:GOVERNS]->(additive)
    {ADDITIVE_RETURN}
    ORDER BY coalesce(entity.ins, entity.name_vi, entity.name, entity.id)
    LIMIT coalesce($limit, 1000000)
    """

    by_id_query = f"""
    MATCH (additive:Additive)
    WHERE coalesce(additive.id, additive.ins, additive.code, elementId(additive)) = $entity_id
    OPTIONAL MATCH (additive)-[:HAS_FUNCTION]->(functionalClass:FunctionalClass)
    OPTIONAL MATCH (additive)-[:PERMITTED_IN]->(foodCategory:FoodCategory)
    OPTIONAL MATCH (additive)-[:SUPPORTED_BY]->(source:Source)
    OPTIONAL MATCH (alias:Alias)-[:REFERS_TO]->(additive)
    OPTIONAL MATCH (regulation:Regulation)-[:GOVERNS]->(additive)
    {ADDITIVE_RETURN}
    """
