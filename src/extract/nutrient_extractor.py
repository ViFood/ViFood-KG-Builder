from src.extract.base import BaseExtractor


NUTRIENT_RETURN = """
RETURN nutrient {
  .*,
  id: coalesce(nutrient.id, nutrient.external_code, nutrient.code, nutrient.name, elementId(nutrient)),
  labels: labels(nutrient)
} AS entity,
{
  sources: [x IN collect(DISTINCT CASE WHEN source IS NULL THEN NULL ELSE source {.*, id: coalesce(source.id, source.code, source.name, elementId(source)), labels: labels(source)} END) WHERE x IS NOT NULL],
  health_claims: [x IN collect(DISTINCT CASE WHEN healthClaim IS NULL THEN NULL ELSE healthClaim {.*, id: coalesce(healthClaim.id, healthClaim.code, healthClaim.name, elementId(healthClaim)), labels: labels(healthClaim)} END) WHERE x IS NOT NULL],
  ingredients: [x IN collect(DISTINCT CASE WHEN ingredient IS NULL THEN NULL ELSE ingredient {.*, id: coalesce(ingredient.id, ingredient.external_code, ingredient.code, ingredient.name, elementId(ingredient)), labels: labels(ingredient)} END) WHERE x IS NOT NULL],
  aliases: [x IN collect(DISTINCT CASE WHEN alias IS NULL THEN NULL ELSE alias {.*, id: coalesce(alias.id, alias.code, alias.name, elementId(alias)), labels: labels(alias)} END) WHERE x IS NOT NULL]
} AS relationships
"""


class NutrientExtractor(BaseExtractor):
    list_query = f"""
    MATCH (nutrient:Nutrient)
    OPTIONAL MATCH (nutrient)-[:SUPPORTED_BY]->(source:Source)
    OPTIONAL MATCH (healthClaim:HealthClaim)-[:SUBJECT_OF]->(nutrient)
    OPTIONAL MATCH (ingredient:Ingredient)-[:HAS_NUTRIENT]->(nutrient)
    OPTIONAL MATCH (alias:Alias)-[:REFERS_TO]->(nutrient)
    {NUTRIENT_RETURN}
    ORDER BY coalesce(entity.name_vi, entity.name, entity.external_code, entity.id)
    LIMIT coalesce($limit, 1000000)
    """

    by_id_query = f"""
    MATCH (nutrient:Nutrient)
    WHERE coalesce(nutrient.id, nutrient.external_code, nutrient.code, elementId(nutrient)) = $entity_id
    OPTIONAL MATCH (nutrient)-[:SUPPORTED_BY]->(source:Source)
    OPTIONAL MATCH (healthClaim:HealthClaim)-[:SUBJECT_OF]->(nutrient)
    OPTIONAL MATCH (ingredient:Ingredient)-[:HAS_NUTRIENT]->(nutrient)
    OPTIONAL MATCH (alias:Alias)-[:REFERS_TO]->(nutrient)
    {NUTRIENT_RETURN}
    """
