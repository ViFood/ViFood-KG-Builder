from src.extract.base import BaseExtractor, cypher_label


INGREDIENT_RETURN = """
RETURN ingredient {
  .*,
  id: coalesce(ingredient.id, ingredient.external_code, ingredient.code, ingredient.name, elementId(ingredient)),
  labels: labels(ingredient)
} AS entity,
{
  groups: [x IN collect(DISTINCT CASE WHEN ingredientGroup IS NULL THEN NULL ELSE ingredientGroup {.*, id: coalesce(ingredientGroup.id, ingredientGroup.code, ingredientGroup.name, elementId(ingredientGroup)), labels: labels(ingredientGroup)} END) WHERE x IS NOT NULL],
  parent_ingredients: [x IN collect(DISTINCT CASE WHEN parentIngredient IS NULL THEN NULL ELSE parentIngredient {.*, id: coalesce(parentIngredient.id, parentIngredient.external_code, parentIngredient.code, parentIngredient.name, elementId(parentIngredient)), labels: labels(parentIngredient)} END) WHERE x IS NOT NULL],
  derived_from: [x IN collect(DISTINCT CASE WHEN sourceIngredient IS NULL THEN NULL ELSE sourceIngredient {.*, id: coalesce(sourceIngredient.id, sourceIngredient.external_code, sourceIngredient.code, sourceIngredient.name, elementId(sourceIngredient)), labels: labels(sourceIngredient)} END) WHERE x IS NOT NULL],
  allergens: [x IN collect(DISTINCT CASE WHEN allergen IS NULL THEN NULL ELSE allergen {.*, id: coalesce(allergen.id, allergen.code, allergen.name, elementId(allergen)), labels: labels(allergen)} END) WHERE x IS NOT NULL],
  nutrients: [x IN collect(DISTINCT CASE WHEN nutrient IS NULL THEN NULL ELSE nutrient {.*, id: coalesce(nutrient.id, nutrient.external_code, nutrient.code, nutrient.name, elementId(nutrient)), labels: labels(nutrient)} END) WHERE x IS NOT NULL],
  sources: [x IN collect(DISTINCT CASE WHEN source IS NULL THEN NULL ELSE source {.*, id: coalesce(source.id, source.code, source.name, elementId(source)), labels: labels(source)} END) WHERE x IS NOT NULL],
  aliases: [x IN collect(DISTINCT CASE WHEN alias IS NULL THEN NULL ELSE alias {.*, id: coalesce(alias.id, alias.code, alias.name, elementId(alias)), labels: labels(alias)} END) WHERE x IS NOT NULL]
} AS relationships
"""


class IngredientExtractor(BaseExtractor):
    def __init__(self, connection, label: str = "Ingredient") -> None:
        super().__init__(connection)
        label = cypher_label(label)
        self.list_query = f"""
    MATCH (ingredient:{label})
    OPTIONAL MATCH (ingredient)-[:IN_GROUP]->(ingredientGroup:IngredientGroup)
    OPTIONAL MATCH (ingredient)-[:IS_A]->(parentIngredient:Ingredient)
    OPTIONAL MATCH (ingredient)-[:DERIVED_FROM]->(sourceIngredient:Ingredient)
    OPTIONAL MATCH (ingredient)-[:CONTAINS_ALLERGEN]->(allergen:Allergen)
    OPTIONAL MATCH (ingredient)-[:HAS_NUTRIENT]->(nutrient:Nutrient)
    OPTIONAL MATCH (ingredient)-[:SUPPORTED_BY]->(source:Source)
    OPTIONAL MATCH (alias:Alias)-[:REFERS_TO]->(ingredient)
    {INGREDIENT_RETURN}
    ORDER BY coalesce(entity.name_vi, entity.name, entity.id)
    LIMIT coalesce($limit, 1000000)
    """

        self.by_id_query = f"""
    MATCH (ingredient:{label})
    WHERE coalesce(ingredient.id, ingredient.external_code, ingredient.code, elementId(ingredient)) = $entity_id
    OPTIONAL MATCH (ingredient)-[:IN_GROUP]->(ingredientGroup:IngredientGroup)
    OPTIONAL MATCH (ingredient)-[:IS_A]->(parentIngredient:Ingredient)
    OPTIONAL MATCH (ingredient)-[:DERIVED_FROM]->(sourceIngredient:Ingredient)
    OPTIONAL MATCH (ingredient)-[:CONTAINS_ALLERGEN]->(allergen:Allergen)
    OPTIONAL MATCH (ingredient)-[:HAS_NUTRIENT]->(nutrient:Nutrient)
    OPTIONAL MATCH (ingredient)-[:SUPPORTED_BY]->(source:Source)
    OPTIONAL MATCH (alias:Alias)-[:REFERS_TO]->(ingredient)
    {INGREDIENT_RETURN}
    """
