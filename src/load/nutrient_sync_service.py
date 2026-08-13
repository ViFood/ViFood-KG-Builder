import json
import re
import unicodedata

from src.config.settings import load_settings
from src.load.runtime_neo4j_service import Neo4jService
from src.prompts.nutrient_duplicate_check import NUTRIENT_DUPLICATE_CHECK_PROMPT


class NutrientSyncService:
    def __init__(self):
        self.settings = load_settings()
        self.neo4j_service = Neo4jService()

    def sync_from_extraction(self, extraction_result: dict) -> list[dict]:
        nutrients = self._normalize_nutrients(
            extraction_result.get("nutritions")
            or extraction_result.get("nutrition")
        )

        if not nutrients:
            return []

        if not self.neo4j_service.is_configured:
            return nutrients

        return [
            self._sync_nutrient(nutrient)
            for nutrient in nutrients
        ]

    def _sync_nutrient(self, nutrient: dict) -> dict:
        existing = self.neo4j_service.match_existing_nutrient(
            nutrient
        )

        if existing:
            return existing

        return self.neo4j_service.sync_nutrient(
            self._ensure_tagname(nutrient)
        )

    def _ensure_tagname(self, nutrient: dict) -> dict:
        if nutrient.get("tagname"):
            return nutrient

        prompt = NUTRIENT_DUPLICATE_CHECK_PROMPT.strip()

        if not prompt or not self.settings.model:
            return nutrient

        try:
            from openai import OpenAI
        except ImportError:
            return nutrient

        response = OpenAI().chat.completions.create(
            model=self.settings.model,
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "system",
                    "content": prompt
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "input_nutrient": nutrient
                        },
                        ensure_ascii=False
                    )
                }
            ],
        )

        result = json.loads(
            response.choices[0].message.content
        )

        tagname = str(
            result.get("tagname") or ""
        ).strip().upper()

        if tagname:
            nutrient["tagname"] = tagname
            nutrient["infoods_name"] = str(
                result.get("infoods_name") or ""
            ).strip()
            nutrient["name_vi"] = str(
                result.get("name_vi") or ""
            ).strip()
            nutrient["default_unit"] = str(
                result.get("default_unit") or ""
            ).strip()

        return nutrient

    def _normalize_nutrients(self, nutrition) -> list[dict]:
        if isinstance(nutrition, list):
            return [
                nutrient
                for item in nutrition
                if isinstance(item, dict)
                for nutrient in [self._normalize_nutrient_item(item)]
                if nutrient["name"]
            ]

        if isinstance(nutrition, dict):
            return [
                {
                    "name": str(name).strip(),
                    "tagname": None,
                    "value": value,
                    "unit": None
                }
                for name, value in nutrition.items()
                if value not in (None, "", [])
            ]

        return []

    def _normalize_nutrient_item(self, item: dict) -> dict:
        name = (
            item.get("name")
            or item.get("label")
            or item.get("nutrient")
            or ""
        )

        name = str(name).strip()

        return {
            "name": name,
            "tagname": self._normalize_tagname(
                item.get("tagname")
            ),
            "infoods_name": item.get("infoods_name"),
            "name_vi": item.get("name_vi"),
            "default_unit": item.get("default_unit"),
            "value": item.get("value"),
            "unit": item.get("unit")
        }

    def _normalize_tagname(self, value) -> str | None:
        if value in (None, ""):
            return None

        return str(value).strip().upper()

    def _normalize_text(self, value: str) -> str:
        normalized = value.strip().lower()
        normalized = unicodedata.normalize("NFD", normalized)
        normalized = "".join(
            char
            for char in normalized
            if unicodedata.category(char) != "Mn"
        )
        normalized = normalized.replace("đ", "d")
        normalized = re.sub(r"[^a-z0-9]+", "_", normalized)
        normalized = normalized.strip("_")

        return normalized
