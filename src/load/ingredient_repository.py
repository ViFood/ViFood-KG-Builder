from __future__ import annotations

import re
import unicodedata
from typing import Any

from src.config.settings import load_settings
from src.load.runtime_neo4j_service import Neo4jService


class IngredientRepository:
    def __init__(self, neo4j_service: Neo4jService | None = None):
        self.neo4j_service = neo4j_service or Neo4jService()
        self.wikidata_settings = load_settings().wikidata

    @property
    def is_configured(self) -> bool:
        return self.neo4j_service.is_configured

    def match_existing(self, ingredient: dict[str, Any]) -> dict[str, Any] | None:
        if not self.is_configured:
            return None

        name = str(ingredient.get("name") or "").strip()
        if not name:
            return None

        normalized_name = self.normalize_name(name)

        return self.neo4j_service._execute_read(
            self._match_existing_tx,
            name,
            normalized_name,
        )

    def sync_from_detail(
        self,
        ingredient: dict[str, Any],
        detail: dict[str, Any],
    ) -> dict[str, Any]:
        if not self.is_configured:
            return {
                "id": None,
                "name": ingredient["name"],
                "status": "unconfigured",
            }

        payload = self.build_graph_payload(ingredient, detail)
        if not payload:
            return {
                "id": None,
                "name": ingredient["name"],
                "status": "unresolved",
            }

        synced = self.neo4j_service._execute_write(
            self._sync_from_payload_tx,
            payload,
        )
        return self._build_sync_result(
            ingredient=ingredient,
            detail=detail,
            ingredient_id=synced["id"],
            status="created",
        )

    def _build_sync_result(
        self,
        *,
        ingredient: dict[str, Any],
        detail: dict[str, Any],
        ingredient_id: str,
        status: str,
    ) -> dict[str, Any]:
        return {
            "id": ingredient_id,
            "name": ingredient["name"],
            "status": status,
            "wikidata_id": detail.get("wikidata_id"),
            "name_vi": detail.get("name_vi"),
            "name_en": detail.get("name_en"),
            "description_vi": detail.get("description_vi"),
            "description_en": detail.get("description_en"),
            "wikipedia_vi_url": detail.get("wikipedia_vi_url"),
            "wikipedia_en_url": detail.get("wikipedia_en_url"),
            "aliases": detail.get("aliases", []),
            "categories": detail.get("categories", []),
            "usages": detail.get("usages", []),
        }

    def build_graph_payload(
        self,
        ingredient: dict[str, Any],
        detail: dict[str, Any],
    ) -> dict[str, Any] | None:
        wikidata_id = str(detail.get("wikidata_id") or "").strip().upper()
        if not wikidata_id:
            return None

        name = (
            detail.get("name_vi")
            or detail.get("name_en")
            or ingredient.get("name")
            or wikidata_id
        )
        ingredient_id = f"INGREDIENT:{wikidata_id}"

        payload = {
            "ingredient": {
                "id": ingredient_id,
                "wikidata_id": wikidata_id,
                "name": name,
                "name_vi": detail.get("name_vi"),
                "name_en": detail.get("name_en"),
                "normalized_name": self.normalize_name(str(name)),
                "description_vi": detail.get("description_vi"),
                "description_en": detail.get("description_en"),
                "wikipedia_vi_url": detail.get("wikipedia_vi_url"),
                "wikipedia_en_url": detail.get("wikipedia_en_url"),
            },
            "source": {
                "id": self.wikidata_settings.source_id,
                "name": self.wikidata_settings.source_name,
                "source_url": self.wikidata_settings.source_url,
            },
            "aliases": self._build_aliases(wikidata_id, ingredient, detail),
            "categories": self._build_categories(detail),
            "usages": self._build_usages(detail),
        }

        return payload

    def _build_aliases(
        self,
        wikidata_id: str,
        ingredient: dict[str, Any],
        detail: dict[str, Any],
    ) -> list[dict[str, Any]]:
        raw_aliases: list[dict[str, Any]] = [
            {
                "name": ingredient.get("name"),
                "language": ingredient.get("language"),
            },
            {
                "name": detail.get("name_vi"),
                "language": "vi",
            },
            {
                "name": detail.get("name_en"),
                "language": "en",
            },
        ]
        raw_aliases.extend(
            alias
            for alias in detail.get("aliases", [])
            if isinstance(alias, dict)
        )

        aliases: list[dict[str, Any]] = []
        seen: set[str] = set()

        for alias in raw_aliases:
            name = str(alias.get("name") or "").strip()
            normalized_name = self.normalize_name(name)
            if not normalized_name or normalized_name in seen:
                continue

            seen.add(normalized_name)
            aliases.append(
                {
                    "id": f"ALIAS:INGREDIENT:{wikidata_id}:{len(aliases) + 1}",
                    "name": name,
                    "normalized_name": normalized_name,
                    "language": alias.get("language") or "unknown",
                }
            )

        return aliases

    def _build_categories(self, detail: dict[str, Any]) -> list[dict[str, Any]]:
        categories: list[dict[str, Any]] = []
        seen: set[str] = set()

        for category in detail.get("categories", []):
            if not isinstance(category, dict):
                continue

            wikidata_id = str(category.get("wikidata_id") or "").strip().upper()
            name = str(category.get("name") or wikidata_id).strip()
            normalized_name = self.normalize_name(name)
            category_id = (
                f"INGREDIENT:{wikidata_id}"
                if wikidata_id
                else f"INGREDIENT:{normalized_name.upper()}"
            )

            if not normalized_name or category_id in seen:
                continue

            seen.add(category_id)
            categories.append(
                {
                    "id": category_id,
                    "wikidata_id": wikidata_id or None,
                    "name": name,
                    "normalized_name": normalized_name,
                }
            )

        return categories

    def _build_usages(self, detail: dict[str, Any]) -> list[dict[str, Any]]:
        usages: list[dict[str, Any]] = []
        seen: set[str] = set()

        for usage in detail.get("usages", []):
            if not isinstance(usage, dict):
                continue

            wikidata_id = str(usage.get("wikidata_id") or "").strip().upper()
            name = str(usage.get("name") or wikidata_id).strip()
            normalized_name = self.normalize_name(name)
            usage_suffix = wikidata_id or normalized_name.upper()
            usage_id = f"INGREDIENT_USAGE:{usage_suffix}"

            if not normalized_name or usage_id in seen:
                continue

            seen.add(usage_id)
            usages.append(
                {
                    "id": usage_id,
                    "wikidata_id": wikidata_id or None,
                    "name": name,
                    "normalized_name": normalized_name,
                }
            )

        return usages

    @staticmethod
    def normalize_name(value: str) -> str:
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

    @staticmethod
    def _match_existing_tx(
        tx,
        name: str,
        normalized_name: str,
    ) -> dict[str, Any] | None:
        match = tx.run(
            """
            MATCH (n:Ingredient)
            WHERE n.normalized_name = $normalized_name
               OR toLower(coalesce(n.name, "")) = $lower_name
               OR toLower(coalesce(n.name_vi, "")) = $lower_name
               OR toLower(coalesce(n.name_en, "")) = $lower_name
            OPTIONAL MATCH (n)<-[:REFERS_TO]-(alias:Alias)
            OPTIONAL MATCH (n)-[:BELONGS_TO]->(category:Ingredient)
            OPTIONAL MATCH (n)-[:HAS_USAGE]->(usage:Usage)
            RETURN n,
                   collect(DISTINCT alias) AS aliases,
                   collect(DISTINCT category) AS categories,
                   collect(DISTINCT usage) AS usages
            LIMIT 1
            """,
            normalized_name=normalized_name,
            lower_name=name.strip().lower(),
        ).single()

        if not match:
            match = tx.run(
                """
                MATCH (a:Alias)-[:REFERS_TO]->(n:Ingredient)
                WHERE a.normalized_name = $normalized_name
                   OR toLower(coalesce(a.name, "")) = $lower_name
                OPTIONAL MATCH (n)<-[:REFERS_TO]-(alias:Alias)
                OPTIONAL MATCH (n)-[:BELONGS_TO]->(category:Ingredient)
                OPTIONAL MATCH (n)-[:HAS_USAGE]->(usage:Usage)
                RETURN n,
                       collect(DISTINCT alias) AS aliases,
                       collect(DISTINCT category) AS categories,
                       collect(DISTINCT usage) AS usages
                LIMIT 1
                """,
                normalized_name=normalized_name,
                lower_name=name.strip().lower(),
            ).single()

        if not match:
            return None

        node = match["n"]
        return {
            "id": node.get("id") or node.element_id,
            "name": name,
            "status": "matched",
            "wikidata_id": node.get("wikidata_id"),
            "name_vi": node.get("name_vi"),
            "name_en": node.get("name_en"),
            "description_vi": node.get("description_vi"),
            "description_en": node.get("description_en"),
            "wikipedia_vi_url": node.get("wikipedia_vi_url"),
            "wikipedia_en_url": node.get("wikipedia_en_url"),
            "aliases": [
                {
                    "name": alias.get("name"),
                    "language": alias.get("language"),
                }
                for alias in match.get("aliases", [])
                if alias and alias.get("name")
            ],
            "categories": [
                {
                    "wikidata_id": category.get("wikidata_id"),
                    "name": category.get("name"),
                }
                for category in match.get("categories", [])
                if category and category.get("name")
            ],
            "usages": [
                {
                    "wikidata_id": usage.get("wikidata_id"),
                    "name": usage.get("name"),
                }
                for usage in match.get("usages", [])
                if usage and usage.get("name")
            ],
        }

    @staticmethod
    def _sync_from_payload_tx(
        tx,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        ingredient = payload["ingredient"]
        source = payload["source"]

        created = tx.run(
            """
            MERGE (i:Ingredient {id: $id})
            ON CREATE SET
                i.wikidata_id = $wikidata_id,
                i.name = $name,
                i.name_vi = $name_vi,
                i.name_en = $name_en,
                i.normalized_name = $normalized_name,
                i.description_vi = $description_vi,
                i.description_en = $description_en,
                i.wikipedia_vi_url = $wikipedia_vi_url,
                i.wikipedia_en_url = $wikipedia_en_url,
                i.status = "active",
                i.created_at = datetime(),
                i.updated_at = datetime()
            ON MATCH SET
                i.wikidata_id = coalesce(i.wikidata_id, $wikidata_id),
                i.name = coalesce(i.name, $name),
                i.name_vi = coalesce(i.name_vi, $name_vi),
                i.name_en = coalesce(i.name_en, $name_en),
                i.normalized_name = coalesce(i.normalized_name, $normalized_name),
                i.description_vi = coalesce(i.description_vi, $description_vi),
                i.description_en = coalesce(i.description_en, $description_en),
                i.wikipedia_vi_url = coalesce(i.wikipedia_vi_url, $wikipedia_vi_url),
                i.wikipedia_en_url = coalesce(i.wikipedia_en_url, $wikipedia_en_url),
                i.status = coalesce(i.status, "active"),
                i.updated_at = datetime()
            MERGE (s:Source {id: $source_id})
            ON CREATE SET
                s.name = $source_name,
                s.source_url = $source_url,
                s.created_at = datetime(),
                s.updated_at = datetime()
            ON MATCH SET
                s.name = coalesce(s.name, $source_name),
                s.source_url = coalesce(s.source_url, $source_url),
                s.updated_at = datetime()
            MERGE (i)-[:SUPPORTED_BY]->(s)
            RETURN i.id AS id
            """,
            **ingredient,
            source_id=source["id"],
            source_name=source["name"],
            source_url=source["source_url"],
        ).single()

        tx.run(
            """
            MATCH (i:Ingredient {id: $ingredient_id})
            UNWIND $aliases AS alias
            MERGE (a:Alias {id: alias.id})
            ON CREATE SET
                a.name = alias.name,
                a.normalized_name = alias.normalized_name,
                a.language = alias.language,
                a.created_at = datetime(),
                a.updated_at = datetime()
            ON MATCH SET
                a.name = coalesce(a.name, alias.name),
                a.normalized_name = coalesce(a.normalized_name, alias.normalized_name),
                a.language = coalesce(a.language, alias.language),
                a.updated_at = datetime()
            MERGE (a)-[:REFERS_TO]->(i)
            """,
            ingredient_id=ingredient["id"],
            aliases=payload["aliases"],
        )

        tx.run(
            """
            MATCH (i:Ingredient {id: $ingredient_id})
            UNWIND $categories AS category
            MERGE (parent:Ingredient {id: category.id})
            ON CREATE SET
                parent.wikidata_id = category.wikidata_id,
                parent.name = category.name,
                parent.normalized_name = category.normalized_name,
                parent.status = "active",
                parent.created_at = datetime(),
                parent.updated_at = datetime()
            ON MATCH SET
                parent.wikidata_id = coalesce(parent.wikidata_id, category.wikidata_id),
                parent.name = coalesce(parent.name, category.name),
                parent.normalized_name = coalesce(parent.normalized_name, category.normalized_name),
                parent.status = coalesce(parent.status, "active"),
                parent.updated_at = datetime()
            MERGE (i)-[:BELONGS_TO]->(parent)
            """,
            ingredient_id=ingredient["id"],
            categories=payload["categories"],
        )

        tx.run(
            """
            MATCH (i:Ingredient {id: $ingredient_id})
            UNWIND $usages AS usage
            MERGE (u:Usage {id: usage.id})
            ON CREATE SET
                u.wikidata_id = usage.wikidata_id,
                u.name = usage.name,
                u.normalized_name = usage.normalized_name,
                u.created_at = datetime(),
                u.updated_at = datetime()
            ON MATCH SET
                u.wikidata_id = coalesce(u.wikidata_id, usage.wikidata_id),
                u.name = coalesce(u.name, usage.name),
                u.normalized_name = coalesce(u.normalized_name, usage.normalized_name),
                u.updated_at = datetime()
            MERGE (i)-[:HAS_USAGE]->(u)
            """,
            ingredient_id=ingredient["id"],
            usages=payload["usages"],
        )

        return {
            "id": created["id"],
        }
