import json

import pytest

from src.extract import AdditiveExtractor, NutrientExtractor
from src.extract.base import cypher_label
from src.load.neo4j_loader import ADDITIVE_IMPORT_QUERY, NUTRIENT_IMPORT_QUERY, Neo4jLoader
from src.main import _items_from_raw, _read_raw_items
from src.services.final_label_response_mapper import FinalLabelResponseMapper


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


def test_final_label_response_preserves_visible_label_fields_only() -> None:
    mapper = FinalLabelResponseMapper()

    response = mapper.build(
        raw_extraction={
            "product_name": "Pineapple juice",
            "age_range": "",
            "ingredients": [
                {"name": "Victoria pineapple", "percentage": 96},
                {"name": "acerola cherry", "percentage": 4},
            ],
            "additive": [],
            "nutrition": {
                "energy": "120",
                "protein": "1g",
                "empty": "",
            },
            "manufacturer": None,
            "net_weight": "250ml",
            "warning": "Shake well",
            "origin": "Vietnam",
            "claims": [
                "100% freshly squeezed fruit",
            ],
            "kg_contract_version": "2026-07-13.1",
            "matched_against_releases": {"nutrient": "release"},
            "source_ref": "s3://bucket/key.jpg",
            "metadata": {"debug": True},
        },
        nutrient_results=[
            {
                "id": "NUTRIENT:INFOODS_PROCNT",
                "name": "Protein",
                "value": "1",
                "unit": "g",
            }
        ],
        additive_results=[],
        ingredient_results=[
            {
                "id": "INGREDIENT:Q123",
                "name": "Victoria pineapple",
                "percentage": 96,
            }
        ],
    )

    assert response["product_name"] == "Pineapple juice"
    assert response["net_weight"] == "250ml"
    assert response["warning"] == "Shake well"
    assert response["origin"] == "Vietnam"
    assert response["claims"] == ["100% freshly squeezed fruit"]
    assert response["ingredients"] == [
        {
            "id": "INGREDIENT:Q123",
            "name": "Victoria pineapple",
            "percentage": 96,
        }
    ]
    assert response["nutrition"]["protein"] == {
        "id": "NUTRIENT:INFOODS_PROCNT",
        "name": "Protein",
        "value": "1",
        "unit": "g",
    }
    assert response["nutrition"]["energy"] == "120"
    assert "additive" not in response
    assert "age_range" not in response
    assert "manufacturer" not in response
    assert "kg_contract_version" not in response
    assert "matched_against_releases" not in response
    assert "source_ref" not in response
    assert "metadata" not in response
