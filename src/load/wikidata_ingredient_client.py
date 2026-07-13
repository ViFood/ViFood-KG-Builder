from __future__ import annotations

import json
from typing import Any

import httpx

from src.config.settings import load_settings


class WikidataIngredientClient:
    def __init__(self):
        self.settings = load_settings().wikidata

    def search_qid(self, name: str) -> str | None:
        search_text = name.strip()
        if not search_text:
            return None

        bindings = self._run_sparql(
            self._search_query(search_text),
            timeout=self.settings.request_timeout_seconds,
        )
        if not bindings:
            return None

        candidate = self._select_food_candidate(
            self._annotate_food_signals(bindings),
            search_text,
        )
        if not candidate:
            return None

        qid = self._binding_value(candidate, "itemId")
        return qid.upper() if qid else None

    def get_detail(self, qid: str) -> dict[str, Any] | None:
        wikidata_id = qid.strip().upper()
        if not wikidata_id:
            return None

        bindings = self._run_sparql(
            self._detail_query(wikidata_id),
            timeout=self.settings.detail_timeout_seconds,
        )
        if not bindings:
            return None

        return self._parse_detail(wikidata_id, bindings)

    def _run_sparql(
        self,
        query: str,
        timeout: int = 30,
    ) -> list[dict[str, Any]]:
        with httpx.Client(timeout=timeout) as client:
            response = client.get(
                self.settings.sparql_url,
                params={
                    "query": query,
                    "format": "json",
                },
                headers={
                    "Accept": "application/sparql-results+json, application/json",
                    "User-Agent": self.settings.user_agent,
                },
            )
            response.raise_for_status()

        return response.json().get("results", {}).get("bindings", [])

    def _parse_detail(
        self,
        wikidata_id: str,
        bindings: list[dict[str, Any]],
    ) -> dict[str, Any]:
        detail: dict[str, Any] = {
            "wikidata_id": wikidata_id,
            "source_url": f"{self.settings.entity_base_url}/{wikidata_id}",
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
            self._set_first_value(detail, "wikipedia_vi_url", row, "wikipediaVi")
            self._set_first_value(detail, "wikipedia_en_url", row, "wikipediaEn")

            self._collect_aliases(aliases, row, "aliasesVi", "vi")
            self._collect_aliases(aliases, row, "aliasesEn", "en")
            self._collect_entities(categories, row, "categories")
            self._collect_entities(usages, row, "uses")

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

    def _collect_aliases(
        self,
        aliases: dict[tuple[str, str], dict[str, str]],
        row: dict[str, Any],
        source_key: str,
        language: str,
    ) -> None:
        values = self._json_binding(row, source_key)
        if not isinstance(values, list):
            return

        for value in values:
            alias = str(value or "").strip()
            if not alias:
                continue
            aliases[(language, alias.lower())] = {
                "name": alias,
                "language": language,
            }

    def _collect_entities(
        self,
        entities: dict[str, dict[str, str]],
        row: dict[str, Any],
        source_key: str,
    ) -> None:
        values = self._json_binding(row, source_key)
        if not isinstance(values, list):
            return

        for value in values:
            if not isinstance(value, dict):
                continue

            wikidata_id = str(value.get("id") or "").strip().upper()
            if not wikidata_id:
                continue

            label = (
                str(value.get("labelVi") or "").strip()
                or str(value.get("labelEn") or "").strip()
                or wikidata_id
            )
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

    def _json_binding(
        self,
        row: dict[str, Any],
        key: str,
    ) -> Any:
        value = self._binding_value(row, key)
        if not value:
            return None

        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return None

    def _select_food_candidate(
        self,
        bindings: list[dict[str, Any]],
        search_text: str = "",
    ) -> dict[str, Any] | None:
        ranked = sorted(
            bindings,
            key=lambda row: (
                self._candidate_food_score(row),
                self._candidate_exact_label_penalty(row, search_text),
                self._candidate_rank(row),
            ),
        )

        if not ranked:
            return None

        best = ranked[0]
        if self._candidate_food_score(best) >= 99:
            return None

        return best

    def _candidate_exact_label_penalty(
        self,
        row: dict[str, Any],
        search_text: str,
    ) -> int:
        normalized_search = self._normalize_search_text(search_text)
        if not normalized_search:
            return 1

        candidate_labels = [
            self._binding_value(row, "nameVi"),
            self._binding_value(row, "nameEn"),
        ]

        if any(
            self._normalize_search_text(label or "") == normalized_search
            for label in candidate_labels
        ):
            return 0

        return 1

    def _annotate_food_signals(
        self,
        bindings: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        qids = [
            qid
            for row in bindings
            for qid in [self._binding_value(row, "itemId")]
            if qid
        ]
        if not qids:
            return bindings

        try:
            signal_rows = self._run_sparql(
                self._food_signal_query(qids),
                timeout=self.settings.request_timeout_seconds,
            )
        except httpx.HTTPError:
            return bindings

        signal_counts = {
            self._binding_value(row, "itemId"): self._binding_int(row, "foodSignalCount")
            for row in signal_rows
        }

        annotated: list[dict[str, Any]] = []
        for row in bindings:
            item_id = self._binding_value(row, "itemId")
            copy = dict(row)
            copy["foodSignalCount"] = {
                "type": "literal",
                "value": str(signal_counts.get(item_id, 0)),
            }
            annotated.append(copy)

        return annotated

    def _candidate_food_score(self, row: dict[str, Any]) -> int:
        if self._binding_int(row, "foodSignalCount") > 0:
            return 0

        text = " ".join(
            value
            for value in [
                self._binding_value(row, "nameVi"),
                self._binding_value(row, "nameEn"),
                self._binding_value(row, "descriptionVi"),
                self._binding_value(row, "descriptionEn"),
            ]
            if value
        ).lower()

        food_keywords = (
            "food",
            "edible",
            "ingredient",
            "fruit",
            "juice",
            "beverage",
            "drink",
            "vitamin",
            "nutrient",
            "carbohydrate",
            "sweet",
            "sugar",
            "thực phẩm",
            "thức ăn",
            "ăn được",
            "lương thực",
            "trái cây",
            "nước ép",
            "vitamin",
        )
        if any(keyword in text for keyword in food_keywords):
            return 1

        non_food_keywords = (
            "road",
            "street",
            "route",
            "transport",
            "thoroughfare",
            "dynasty",
            "surname",
            "family name",
            "commune",
            "district",
            "province",
            "đường đi",
            "lộ trình",
            "giao thông",
            "hoàng triều",
            "họ",
            "xã",
            "huyện",
            "tỉnh",
        )
        if any(keyword in text for keyword in non_food_keywords):
            return 99

        return 10

    def _candidate_rank(self, row: dict[str, Any]) -> int:
        return self._binding_int(row, "rank") or 9999

    def _binding_int(
        self,
        row: dict[str, Any],
        key: str,
    ) -> int:
        value = self._binding_value(row, key)
        if value in (None, ""):
            return 0

        try:
            return int(float(value))
        except ValueError:
            return 0

    def _search_query(self, search_text: str) -> str:
        return f"""
PREFIX wikibase: <http://wikiba.se/ontology#>
PREFIX bd: <http://www.bigdata.com/rdf#>
PREFIX mwapi: <https://www.mediawiki.org/ontology#API/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX schema: <http://schema.org/>

SELECT DISTINCT
  ?itemId
  ?nameVi
  ?nameEn
  ?descriptionVi
  ?descriptionEn
  ?rank
WHERE {{
  BIND("{self._sparql_string(search_text)}" AS ?searchText)

  SERVICE wikibase:mwapi {{
    bd:serviceParam
      wikibase:endpoint "www.wikidata.org";
      wikibase:api "EntitySearch";
      mwapi:search ?searchText;
      mwapi:language "{self._sparql_string(self.settings.search_language)}";
      mwapi:type "item";
      mwapi:limit "{self.settings.search_limit}".

    ?item wikibase:apiOutputItem mwapi:item.
    ?rank wikibase:apiOrdinal true.
  }}

  OPTIONAL {{
    ?item rdfs:label ?nameVi.
    FILTER(LANG(?nameVi) = "vi")
  }}

  OPTIONAL {{
    ?item rdfs:label ?nameEn.
    FILTER(LANG(?nameEn) = "en")
  }}

  OPTIONAL {{
    ?item schema:description ?descriptionVi.
    FILTER(LANG(?descriptionVi) = "vi")
  }}

  OPTIONAL {{
    ?item schema:description ?descriptionEn.
    FILTER(LANG(?descriptionEn) = "en")
  }}

  BIND(REPLACE(STR(?item), "^.*/", "") AS ?itemId)
}}
ORDER BY ASC(?rank)
LIMIT {self.settings.search_limit}
"""

    def _food_signal_query(
        self,
        qids: list[str],
    ) -> str:
        values = " ".join(
            f"wd:{self._sparql_qid(qid)}"
            for qid in qids
        )
        food_signal_values = " ".join(
            f"wd:{self._sparql_qid(qid)}"
            for qid in self.settings.food_signal_qids
        )

        return f"""
PREFIX wdt: <http://www.wikidata.org/prop/direct/>
PREFIX wd: <http://www.wikidata.org/entity/>

SELECT
  ?itemId
  (COUNT(?foodSignal) AS ?foodSignalCount)
WHERE {{
  VALUES ?item {{ {values} }}

  OPTIONAL {{
    ?item (wdt:P31|wdt:P279|wdt:P366)/(wdt:P279*) ?foodSignal.
    VALUES ?foodSignal {{ {food_signal_values} }}
  }}

  BIND(REPLACE(STR(?item), "^.*/", "") AS ?itemId)
}}
GROUP BY ?item ?itemId
"""

    def _detail_query(self, wikidata_id: str) -> str:
        return f"""
PREFIX wd: <http://www.wikidata.org/entity/>
PREFIX wdt: <http://www.wikidata.org/prop/direct/>
PREFIX schema: <http://schema.org/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>

SELECT
  ?item
  ?nameVi
  ?nameEn
  ?descriptionVi
  ?descriptionEn
  ?aliasesVi
  ?aliasesEn
  ?categories
  ?uses
  ?wikipediaVi
  ?wikipediaEn

WHERE {{
  BIND(wd:{wikidata_id} AS ?item)

  OPTIONAL {{
    ?item rdfs:label ?nameVi.
    FILTER(LANG(?nameVi) = "vi")
  }}

  OPTIONAL {{
    ?item rdfs:label ?nameEn.
    FILTER(LANG(?nameEn) = "en")
  }}

  OPTIONAL {{
    ?item schema:description ?descriptionVi.
    FILTER(LANG(?descriptionVi) = "vi")
  }}

  OPTIONAL {{
    ?item schema:description ?descriptionEn.
    FILTER(LANG(?descriptionEn) = "en")
  }}

  OPTIONAL {{
    SELECT
      ?item
      (CONCAT(
        "[",
        GROUP_CONCAT(
          DISTINCT CONCAT(
            '"',
            REPLACE(STR(?aliasVi), '"', '\\\\"'),
            '"'
          );
          SEPARATOR=","
        ),
        "]"
      ) AS ?aliasesVi)
    WHERE {{
      BIND(wd:{wikidata_id} AS ?item)
      ?item skos:altLabel ?aliasVi.
      FILTER(LANG(?aliasVi) = "vi")
    }}
    GROUP BY ?item
  }}

  OPTIONAL {{
    SELECT
      ?item
      (CONCAT(
        "[",
        GROUP_CONCAT(
          DISTINCT CONCAT(
            '"',
            REPLACE(STR(?aliasEn), '"', '\\\\"'),
            '"'
          );
          SEPARATOR=","
        ),
        "]"
      ) AS ?aliasesEn)
    WHERE {{
      BIND(wd:{wikidata_id} AS ?item)
      ?item skos:altLabel ?aliasEn.
      FILTER(LANG(?aliasEn) = "en")
    }}
    GROUP BY ?item
  }}

  OPTIONAL {{
    SELECT
      ?item
      (CONCAT(
        "[",
        GROUP_CONCAT(
          DISTINCT CONCAT(
            '{{"id":"',
            REPLACE(STR(?category), "^.*/", ""),
            '","labelVi":"',
            REPLACE(COALESCE(STR(?categoryLabelVi), ""), '"', '\\\\"'),
            '","labelEn":"',
            REPLACE(COALESCE(STR(?categoryLabelEn), ""), '"', '\\\\"'),
            '"}}'
          );
          SEPARATOR=","
        ),
        "]"
      ) AS ?categories)
    WHERE {{
      BIND(wd:{wikidata_id} AS ?item)
      ?item wdt:P279 ?category.

      OPTIONAL {{
        ?category rdfs:label ?categoryLabelVi.
        FILTER(LANG(?categoryLabelVi) = "vi")
      }}

      OPTIONAL {{
        ?category rdfs:label ?categoryLabelEn.
        FILTER(LANG(?categoryLabelEn) = "en")
      }}
    }}
    GROUP BY ?item
  }}

  OPTIONAL {{
    SELECT
      ?item
      (CONCAT(
        "[",
        GROUP_CONCAT(
          DISTINCT CONCAT(
            '{{"id":"',
            REPLACE(STR(?use), "^.*/", ""),
            '","labelVi":"',
            REPLACE(COALESCE(STR(?useLabelVi), ""), '"', '\\\\"'),
            '","labelEn":"',
            REPLACE(COALESCE(STR(?useLabelEn), ""), '"', '\\\\"'),
            '"}}'
          );
          SEPARATOR=","
        ),
        "]"
      ) AS ?uses)
    WHERE {{
      BIND(wd:{wikidata_id} AS ?item)
      ?item wdt:P366 ?use.

      OPTIONAL {{
        ?use rdfs:label ?useLabelVi.
        FILTER(LANG(?useLabelVi) = "vi")
      }}

      OPTIONAL {{
        ?use rdfs:label ?useLabelEn.
        FILTER(LANG(?useLabelEn) = "en")
      }}
    }}
    GROUP BY ?item
  }}

  OPTIONAL {{
    ?wikipediaVi schema:about ?item;
                 schema:isPartOf <https://vi.wikipedia.org/>.
  }}

  OPTIONAL {{
    ?wikipediaEn schema:about ?item;
                 schema:isPartOf <https://en.wikipedia.org/>.
  }}
}}
"""

    @staticmethod
    def _sparql_string(value: str) -> str:
        return (
            value
            .replace("\\", "\\\\")
            .replace('"', '\\"')
            .replace("\n", "\\n")
            .replace("\r", "\\r")
        )

    @staticmethod
    def _sparql_qid(value: str) -> str:
        normalized = value.strip().upper()
        if not normalized.startswith("Q") or not normalized[1:].isdigit():
            raise ValueError(f"Invalid Wikidata QID: {value}")
        return normalized

    @staticmethod
    def _normalize_search_text(value: str) -> str:
        return " ".join(value.strip().casefold().split())
