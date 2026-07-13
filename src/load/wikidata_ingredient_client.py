from __future__ import annotations

from typing import Any

import httpx


class WikidataIngredientClient:
    search_url = "https://www.wikidata.org/w/api.php"
    sparql_url = "https://query.wikidata.org/sparql"

    def search_qid(self, name: str) -> str | None:
        query = name.strip()
        if not query:
            return None

        for language in ("vi", "en"):
            qid = self._search_qid_by_language(query, language)
            if qid:
                return qid

        return None

    def get_detail(self, qid: str) -> dict[str, Any] | None:
        wikidata_id = qid.strip().upper()
        if not wikidata_id:
            return None

        query = self._detail_query(wikidata_id)

        with httpx.Client(timeout=30) as client:
            response = client.get(
                self.sparql_url,
                params={
                    "query": query,
                    "format": "json",
                },
                headers={
                    "Accept": "application/sparql-results+json",
                    "User-Agent": "ViFood-KG-Builder/1.0",
                },
            )
            response.raise_for_status()

        bindings = response.json().get("results", {}).get("bindings", [])
        if not bindings:
            return None

        return self._parse_detail(wikidata_id, bindings)

    def _search_qid_by_language(self, name: str, language: str) -> str | None:
        with httpx.Client(timeout=15) as client:
            response = client.get(
                self.search_url,
                params={
                    "action": "wbsearchentities",
                    "format": "json",
                    "language": language,
                    "uselang": language,
                    "type": "item",
                    "limit": 1,
                    "search": name,
                },
                headers={
                    "User-Agent": "ViFood-KG-Builder/1.0",
                },
            )
            response.raise_for_status()

        search = response.json().get("search", [])
        if not search:
            return None

        qid = str(search[0].get("id") or "").strip().upper()
        return qid or None

    def _parse_detail(
        self,
        wikidata_id: str,
        bindings: list[dict[str, Any]],
    ) -> dict[str, Any]:
        detail: dict[str, Any] = {
            "wikidata_id": wikidata_id,
            "source_url": f"https://www.wikidata.org/wiki/{wikidata_id}",
            "aliases": [],
            "categories": [],
            "usages": [],
        }
        aliases: dict[tuple[str, str], dict[str, str]] = {}
        categories: dict[str, dict[str, str]] = {}
        usages: dict[str, dict[str, str]] = {}

        for row in bindings:
            self._set_first_value(detail, "name_vi", row, "nameVi")
            self._set_first_value(detail, "name_en", row, "nameEn")
            self._set_first_value(detail, "description_vi", row, "descriptionVi")
            self._set_first_value(detail, "description_en", row, "descriptionEn")
            self._set_first_value(detail, "wikipedia_vi_url", row, "articleVi")
            self._set_first_value(detail, "wikipedia_en_url", row, "articleEn")

            self._collect_alias(aliases, row, "aliasVi", "vi")
            self._collect_alias(aliases, row, "aliasEn", "en")
            self._collect_entity(categories, row, "category", "categoryLabel")
            self._collect_entity(usages, row, "usage", "usageLabel")

        detail["aliases"] = list(aliases.values())
        detail["categories"] = list(categories.values())
        detail["usages"] = list(usages.values())

        return detail

    def _set_first_value(
        self,
        target: dict[str, Any],
        target_key: str,
        row: dict[str, Any],
        source_key: str,
    ) -> None:
        if target.get(target_key):
            return

        value = self._binding_value(row, source_key)
        if value:
            target[target_key] = value

    def _collect_alias(
        self,
        aliases: dict[tuple[str, str], dict[str, str]],
        row: dict[str, Any],
        source_key: str,
        language: str,
    ) -> None:
        value = self._binding_value(row, source_key)
        if not value:
            return

        aliases[(language, value.strip().lower())] = {
            "name": value,
            "language": language,
        }

    def _collect_entity(
        self,
        entities: dict[str, dict[str, str]],
        row: dict[str, Any],
        id_key: str,
        label_key: str,
    ) -> None:
        uri = self._binding_value(row, id_key)
        if not uri:
            return

        wikidata_id = uri.rsplit("/", 1)[-1]
        label = self._binding_value(row, label_key) or wikidata_id
        entities[wikidata_id] = {
            "wikidata_id": wikidata_id,
            "name": label,
        }

    def _binding_value(
        self,
        row: dict[str, Any],
        key: str,
    ) -> str | None:
        value = row.get(key, {}).get("value")
        if value in (None, ""):
            return None
        return str(value).strip()

    def _detail_query(self, wikidata_id: str) -> str:
        return f"""
PREFIX wd: <http://www.wikidata.org/entity/>
PREFIX wdt: <http://www.wikidata.org/prop/direct/>
PREFIX schema: <http://schema.org/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>

SELECT ?nameVi ?nameEn ?descriptionVi ?descriptionEn
       ?articleVi ?articleEn ?aliasVi ?aliasEn
       ?category ?categoryLabel ?usage ?usageLabel
WHERE {{
  BIND(wd:{wikidata_id} AS ?item)
  OPTIONAL {{ ?item rdfs:label ?nameVi FILTER(LANG(?nameVi) = "vi") }}
  OPTIONAL {{ ?item rdfs:label ?nameEn FILTER(LANG(?nameEn) = "en") }}
  OPTIONAL {{ ?item schema:description ?descriptionVi FILTER(LANG(?descriptionVi) = "vi") }}
  OPTIONAL {{ ?item schema:description ?descriptionEn FILTER(LANG(?descriptionEn) = "en") }}
  OPTIONAL {{ ?item skos:altLabel ?aliasVi FILTER(LANG(?aliasVi) = "vi") }}
  OPTIONAL {{ ?item skos:altLabel ?aliasEn FILTER(LANG(?aliasEn) = "en") }}
  OPTIONAL {{
    ?articleVi schema:about ?item ;
               schema:isPartOf <https://vi.wikipedia.org/> .
  }}
  OPTIONAL {{
    ?articleEn schema:about ?item ;
               schema:isPartOf <https://en.wikipedia.org/> .
  }}
  OPTIONAL {{
    ?item wdt:P31|wdt:P279 ?category .
    OPTIONAL {{ ?category rdfs:label ?categoryLabel FILTER(LANG(?categoryLabel) IN ("vi", "en")) }}
  }}
  OPTIONAL {{
    ?item wdt:P366 ?usage .
    OPTIONAL {{ ?usage rdfs:label ?usageLabel FILTER(LANG(?usageLabel) IN ("vi", "en")) }}
  }}
}}
LIMIT 200
"""
