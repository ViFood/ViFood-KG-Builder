from __future__ import annotations

from typing import Any

import httpx
from neo4j.exceptions import DriverError, Neo4jError

from src.load.ingredient_repository import IngredientRepository
from src.load.wikidata_ingredient_client import WikidataIngredientClient


class IngredientSyncService:
    def __init__(
        self,
        repository: IngredientRepository | None = None,
        wikidata_client: WikidataIngredientClient | None = None,
    ):
        self.repository = repository or IngredientRepository()
        self.wikidata_client = wikidata_client or WikidataIngredientClient()

    def sync_from_extraction(self, extraction_result: dict[str, Any]) -> list[dict[str, Any]]:
        ingredients = self._normalize_ingredients(
            extraction_result.get("ingredients")
            or extraction_result.get("ingredient")
        )

        if not ingredients:
            return []

        if not self.repository.is_configured:
            return []

        return [
            self._sync_ingredient(ingredient)
            for ingredient in ingredients
        ]

    def _sync_ingredient(self, ingredient: dict[str, Any]) -> dict[str, Any]:
        try:
            existing = self.repository.match_existing(ingredient)
        except (DriverError, Neo4jError):
            existing = None

        if existing:
            return existing

        try:
            qid = self.wikidata_client.search_qid(ingredient["name"])
            if not qid:
                return self._unresolved(ingredient)

            detail = self.wikidata_client.get_detail(qid)
            if not detail:
                return self._unresolved(ingredient)

            detail["wikidata_id"] = detail.get("wikidata_id") or qid
            return self.repository.sync_from_detail(ingredient, detail)
        except (DriverError, httpx.HTTPError, Neo4jError, ValueError):
            return self._unresolved(ingredient)

    def _normalize_ingredients(self, ingredients: Any) -> list[dict[str, Any]]:
        raw_items = ingredients if isinstance(ingredients, list) else [ingredients]
        normalized_items: list[dict[str, Any]] = []
        seen: set[str] = set()

        for item in raw_items:
            name = self._extract_name(item)
            if not name:
                continue

            normalized_name = IngredientRepository.normalize_name(name)
            if not normalized_name or normalized_name in seen:
                continue

            seen.add(normalized_name)
            normalized_items.append(
                {
                    "name": name,
                    "normalized_name": normalized_name,
                }
            )

        return normalized_items

    def _extract_name(self, item: Any) -> str | None:
        if item in (None, "", [], {}):
            return None

        if isinstance(item, dict):
            value = (
                item.get("name")
                or item.get("label")
                or item.get("ingredients")
                or item.get("ingredient")
            )
        else:
            value = item

        name = str(value or "").strip()
        return name or None

    def _unresolved(self, ingredient: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": None,
            "name": ingredient["name"],
            "status": "unresolved",
        }
