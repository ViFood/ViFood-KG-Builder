import json

import pytest

from src.extract import AdditiveExtractor, NutrientExtractor
from src.extract.base import cypher_label
from src.load.neo4j_loader import ADDITIVE_IMPORT_QUERY, NUTRIENT_IMPORT_QUERY, Neo4jLoader
from src.main import _items_from_raw, _read_raw_items


def test_read_raw_items_filters_type_and_limit(tmp_path) -> None:
    raw_file = tmp_path / "raw_all.json"
    raw_file.write_text(
        json.dumps(
            {
                "items": [
                    {
                        "entity_type": "legacy_entity",
                        "entity": {"id": "legacy:rice"},
                        "relationships": {},
                    },
                    {
                        "entity_type": "additive",
                        "entity": {"id": "additive:e330"},
                        "relationships": {"sources": [{"id": "source:test"}]},
                    },
                    {
                        "entity_type": "nutrient",
                        "entity": {"id": "nutrient:protein"},
                        "relationships": {},
                    },
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    raw_items = _read_raw_items(raw_file, "additive", limit=1)

    assert raw_items == [
        (
            "additive",
            {
                "entity": {"id": "additive:e330"},
                "relationships": {"sources": [{"id": "source:test"}]},
            },
        )
    ]

    all_raw_items = _read_raw_items(raw_file, "all")

    assert [item[0] for item in all_raw_items] == ["additive", "nutrient"]


def test_items_from_raw_preserves_source_payload() -> None:
    raw_items = [
        (
            "additive",
            {
                "entity": {"id": "additive:e330", "name": "Citric acid"},
                "relationships": {"functions": [{"id": "function:acid"}]},
            },
        )
    ]

    assert _items_from_raw(raw_items) == [
        {
            "entity_type": "additive",
            "entity": {"id": "additive:e330", "name": "Citric acid"},
            "relationships": {"functions": [{"id": "function:acid"}]},
        }
    ]


def test_loader_validates_raw_import_payload() -> None:
    payload = {
        "items": [
            {
                "entity_type": "additive",
                "entity": {"id": "additive:e330", "name": "Citric acid"},
                "relationships": {},
            },
            {
                "entity_type": "nutrient",
                "entity": {"id": "nutrient:protein", "name": "Protein"},
                "relationships": {"sources": [{"id": "source:test"}]},
            },
        ]
    }

    Neo4jLoader.validate_payload(payload)


def test_loader_rejects_wiki_payload() -> None:
    with pytest.raises(ValueError, match="entity must be an object"):
        Neo4jLoader.validate_payload(
            {
                "items": [
                    {
                        "entity_type": "additive",
                        "entity_id": "additive:e330",
                        "wiki_profile": {},
                        "wiki_sections": [],
                    }
                ]
            }
        )


def test_import_queries_do_not_create_wiki_nodes() -> None:
    combined_query = ADDITIVE_IMPORT_QUERY + NUTRIENT_IMPORT_QUERY

    assert "WikiProfile" not in combined_query
    assert "WikiSection" not in combined_query
    assert "HAS_WIKI_PROFILE" not in combined_query
    assert "HAS_SECTION" not in combined_query


def test_extractors_use_configured_entity_labels() -> None:
    additive = AdditiveExtractor(connection=None, label="FoodAdditive")
    nutrient = NutrientExtractor(connection=None, label="FoodNutrient")

    assert "MATCH (additive:FoodAdditive)" in additive.list_query
    assert "MATCH (nutrient:FoodNutrient)" in nutrient.list_query


def test_cypher_label_rejects_unsafe_values() -> None:
    for label in ("", "1Additive", "Additive) MATCH (n", "Food-Additive"):
        with pytest.raises(ValueError):
            cypher_label(label)
