from __future__ import annotations

from typing import Any

from src.schemas.product_label import FinalLabelResponse, PublicLabelEntity


LABEL_VISIBLE_FIELDS = {
    "product_name",
    "age_range",
    "manufacturer",
    "mfg_date",
    "expiry_date",
    "net_weight",
    "warning",
    "origin",
}

INTERNAL_FIELDS = {
    "kg_contract_version",
    "matched_against_releases",
    "source_ref",
    "provenance",
    "source",
    "sources",
    "status",
    "errors",
    "error",
    "debug",
    "metadata",
    "graph_payload",
    "relationships",
    "wikidata_id",
    "wikipedia_vi_url",
    "wikipedia_en_url",
}

GROUP_FIELDS = {
    "ingredients",
    "ingredient",
    "additive",
    "additives",
    "nutrition",
    "nutritions",
    "nutrients",
}


class FinalLabelResponseMapper:
    def build(
        self,
        raw_extraction: dict[str, Any],
        nutrient_results: list[dict[str, Any]] | None = None,
        additive_results: list[dict[str, Any]] | None = None,
        ingredient_results: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        response_data: dict[str, Any] = {}

        for key, value in raw_extraction.items():
            if key in INTERNAL_FIELDS or key in GROUP_FIELDS:
                continue
            if key in LABEL_VISIBLE_FIELDS or self._is_label_visible_extra(value):
                self._set_if_present(response_data, key, value)

        nutrition = self._build_nutrition(raw_extraction, nutrient_results or [])
        if nutrition:
            response_data["nutritions"] = nutrition

        ingredients = self._build_ingredient_entities(ingredient_results or [])
        if ingredients:
            response_data["ingredients"] = ingredients

        additives = self._build_entities(additive_results or [])
        if not additives:
            additives = self._build_raw_entities(
                raw_extraction.get("additives")
                or raw_extraction.get("additive")
            )
        if additives:
            response_data["additives"] = additives

        return FinalLabelResponse(**response_data).model_dump(
            exclude_none=True,
            exclude_defaults=True,
            exclude_unset=True,
        )

    def _build_nutrition(
        self,
        raw_extraction: dict[str, Any],
        nutrient_results: list[dict[str, Any]],
    ) -> dict[str, Any]:
        raw_nutrition = (
            raw_extraction.get("nutritions")
            or raw_extraction.get("nutrition")
        )
        nutrition: dict[str, Any] = {}

        if isinstance(raw_nutrition, dict):
            for key, value in raw_nutrition.items():
                self._set_if_present(nutrition, str(key), value)

        for nutrient in nutrient_results:
            if not isinstance(nutrient, dict):
                continue
            name = nutrient.get("name")
            if not name:
                continue
            item = self._compact_dict(
                {
                    "id": nutrient.get("id"),
                    "name": name,
                    "value": nutrient.get("value"),
                    "unit": nutrient.get("unit"),
                    "daily_value_percent": nutrient.get("daily_value_percent"),
                }
            )
            if item.get("id") and item.get("name"):
                nutrition[self._normalize_key(str(name))] = item

        if isinstance(raw_nutrition, list):
            for item in raw_nutrition:
                if not isinstance(item, dict):
                    continue
                name = item.get("name") or item.get("label") or item.get("nutrient")
                if not name:
                    continue
                key = self._normalize_key(str(name))
                nutrition.setdefault(
                    key,
                    self._compact_dict(
                        {
                            "name": str(name),
                            "value": item.get("value"),
                            "unit": item.get("unit"),
                            "daily_value_percent": item.get("daily_value_percent"),
                        }
                    ),
                )

        return nutrition

    def _build_entities(self, results: list[dict[str, Any]]) -> list[dict[str, Any]]:
        entities: list[dict[str, Any]] = []
        seen: set[tuple[str, str]] = set()

        for result in results:
            if not isinstance(result, dict):
                continue
            entity = self._entity_from_result(result)
            if not entity:
                continue
            key = (entity.id or "", entity.name)
            if key in seen:
                continue
            seen.add(key)
            entities.append(
                entity.model_dump(
                    exclude_none=True,
                    exclude_defaults=True,
                    exclude_unset=True,
                )
            )

        return entities

    def _build_ingredient_entities(
        self,
        results: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        return self._build_entities(
            [
                result
                for result in results
                if self._has_wikidata_ingredient_detail(result)
            ]
        )

    def _has_wikidata_ingredient_detail(self, result: dict[str, Any]) -> bool:
        if not isinstance(result, dict):
            return False

        if result.get("status") == "unresolved":
            return False

        if not result.get("id") or not result.get("wikidata_id"):
            return False

        return any(
            self._is_present(result.get(key))
            for key in (
                "description_vi",
                "description_en",
                "wikipedia_vi_url",
                "wikipedia_en_url",
                "aliases",
                "categories",
                "usages",
            )
        )

    def _build_raw_entities(self, raw_value: Any) -> list[dict[str, Any]]:
        raw_items = raw_value if isinstance(raw_value, list) else [raw_value]
        entities: list[dict[str, Any]] = []
        seen: set[str] = set()

        for item in raw_items:
            entity = self._raw_entity_from_item(item)
            if not entity:
                continue
            key = entity.name.strip().lower()
            if key in seen:
                continue
            seen.add(key)
            entities.append(
                entity.model_dump(
                    exclude_none=True,
                    exclude_defaults=True,
                    exclude_unset=True,
                )
            )

        return entities

    def _raw_entity_from_item(self, item: Any) -> PublicLabelEntity | None:
        if item in (None, "", [], {}):
            return None

        if isinstance(item, dict):
            name = (
                item.get("name")
                or item.get("label")
                or item.get("ingredient")
                or item.get("ingredients")
                or item.get("additive")
                or item.get("additives")
            )
            if not name:
                return None
            return PublicLabelEntity(
                id=item.get("id"),
                name=str(name),
                percentage=item.get("percentage"),
                ins=item.get("ins") or item.get("code"),
            )

        return PublicLabelEntity(name=str(item).strip())

    def _entity_from_result(self, result: dict[str, Any]) -> PublicLabelEntity | None:
        entity_id = result.get("id") or result.get("matched_entity_id")
        name = result.get("name")

        if not name:
            return None

        return PublicLabelEntity(
            id=str(entity_id) if entity_id else None,
            name=str(name),
            value=result.get("value"),
            unit=result.get("unit"),
            percentage=result.get("percentage"),
            daily_value_percent=result.get("daily_value_percent"),
            ins=result.get("ins"),
            wikidata_id=result.get("wikidata_id"),
            name_vi=result.get("name_vi"),
            name_en=result.get("name_en"),
            description_vi=result.get("description_vi"),
            description_en=result.get("description_en"),
            wikipedia_vi_url=result.get("wikipedia_vi_url"),
            wikipedia_en_url=result.get("wikipedia_en_url"),
            aliases=result.get("aliases"),
            categories=result.get("categories"),
            usages=result.get("usages"),
        )

    def _set_if_present(self, target: dict[str, Any], key: str, value: Any) -> None:
        if self._is_present(value):
            target[key] = value

    def _is_present(self, value: Any) -> bool:
        return value not in (None, "", [], {})

    def _is_label_visible_extra(self, value: Any) -> bool:
        return isinstance(value, (str, int, float, bool, list, dict)) and self._is_present(value)

    def _compact_dict(self, data: dict[str, Any]) -> dict[str, Any]:
        return {
            key: value
            for key, value in data.items()
            if self._is_present(value)
        }

    def _normalize_key(self, value: str) -> str:
        normalized = value.strip().lower()
        replacements = {
            "total fat": "fat",
            "saturated fat": "saturated_fat",
            "trans fat": "trans_fat",
            "total carbohydrate": "carbohydrate",
            "dietary fiber": "fiber",
            "total sugars": "sugar",
            "added sugars": "added_sugar",
            "calories": "energy",
        }
        if normalized in replacements:
            return replacements[normalized]
        return "_".join(part for part in normalized.replace("-", " ").split() if part)
