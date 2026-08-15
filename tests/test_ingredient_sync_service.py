from src.load.ingredient_repository import IngredientRepository
from src.load.ingredient_sync_service import IngredientSyncService
from src.load.wikidata_ingredient_client import WikidataIngredientClient
from neo4j.exceptions import ServiceUnavailable


class FakeIngredientRepository:
    def __init__(self, existing=None, fail_match=False, fail_sync=False):
        self.is_configured = True
        self.existing = existing
        self.fail_match = fail_match
        self.fail_sync = fail_sync
        self.created = []

    def match_existing(self, ingredient):
        if self.fail_match:
            raise ServiceUnavailable("neo4j read unavailable")
        return self.existing

    def sync_from_detail(self, ingredient, detail):
        if self.fail_sync:
            raise ServiceUnavailable("neo4j write unavailable")
        self.created.append((ingredient, detail))
        return {
            "id": f"INGREDIENT:{detail['wikidata_id']}",
            "name": ingredient["name"],
            "status": "created",
        }


class FakeUnconfiguredIngredientRepository(FakeIngredientRepository):
    def __init__(self):
        super().__init__()
        self.is_configured = False


class FakeWikidataClient:
    def __init__(self, qid="Q10943", detail=None):
        self.qid = qid
        self.detail = detail
        self.search_calls = []
        self.detail_calls = []

    def search_qid(self, name):
        self.search_calls.append(name)
        return self.qid

    def get_detail(self, qid):
        self.detail_calls.append(qid)
        return self.detail


def test_ingredient_sync_matches_existing_before_wikidata() -> None:
    repository = FakeIngredientRepository(
        existing={
            "id": "INGREDIENT:Q10943",
            "name": "sugar",
            "status": "matched",
        }
    )
    wikidata = FakeWikidataClient()
    service = IngredientSyncService(repository=repository, wikidata_client=wikidata)

    result = service.sync_from_extraction(
        {
            "ingredients": [
                "sugar",
            ]
        }
    )

    assert result == [
        {
            "id": "INGREDIENT:Q10943",
            "name": "sugar",
            "status": "matched",
        }
    ]
    assert wikidata.search_calls == []
    assert wikidata.detail_calls == []


def test_ingredient_sync_creates_missing_ingredient_from_wikidata_detail() -> None:
    detail = {
        "wikidata_id": "Q10943",
        "name_vi": "đường",
        "name_en": "sugar",
        "description_vi": "chất tạo vị ngọt",
        "description_en": "sweet substance",
        "aliases": [
            {
                "name": "table sugar",
                "language": "en",
            }
        ],
        "categories": [
            {
                "wikidata_id": "Q2095",
                "name": "food",
            }
        ],
        "usages": [
            {
                "wikidata_id": "Q193619",
                "name": "sweetener",
            }
        ],
    }
    repository = FakeIngredientRepository()
    wikidata = FakeWikidataClient(detail=detail)
    service = IngredientSyncService(repository=repository, wikidata_client=wikidata)

    result = service.sync_from_extraction(
        {
            "ingredients": [
                {
                    "name": "sugar",
                    "percentage": 12,
                }
            ]
        }
    )

    assert result == [
        {
            "id": "INGREDIENT:Q10943",
            "name": "sugar",
            "status": "created",
        }
    ]
    assert wikidata.search_calls == ["sugar"]
    assert wikidata.detail_calls == ["Q10943"]
    assert repository.created[0][0] == {
        "name": "sugar",
        "normalized_name": "sugar",
    }


def test_ingredient_sync_returns_empty_when_repository_is_unconfigured() -> None:
    repository = FakeUnconfiguredIngredientRepository()
    wikidata = FakeWikidataClient()
    service = IngredientSyncService(repository=repository, wikidata_client=wikidata)

    result = service.sync_from_extraction(
        {
            "ingredients": [
                "sugar",
            ]
        }
    )

    assert result == []
    assert wikidata.search_calls == []
    assert wikidata.detail_calls == []


def test_ingredient_sync_uses_wikidata_when_neo4j_match_fails() -> None:
    detail = {
        "wikidata_id": "Q11002",
        "name_vi": "đường",
        "name_en": "sugar",
    }
    repository = FakeIngredientRepository(fail_match=True)
    wikidata = FakeWikidataClient(qid="Q11002", detail=detail)
    service = IngredientSyncService(repository=repository, wikidata_client=wikidata)

    result = service.sync_from_extraction(
        {
            "ingredients": [
                "sugar",
            ]
        }
    )

    assert result == [
        {
            "id": "INGREDIENT:Q11002",
            "name": "sugar",
            "status": "created",
        }
    ]
    assert wikidata.search_calls == ["sugar"]
    assert wikidata.detail_calls == ["Q11002"]


def test_ingredient_sync_returns_unresolved_when_neo4j_write_fails() -> None:
    detail = {
        "wikidata_id": "Q11002",
        "name_vi": "đường",
        "name_en": "sugar",
    }
    repository = FakeIngredientRepository(fail_sync=True)
    wikidata = FakeWikidataClient(qid="Q11002", detail=detail)
    service = IngredientSyncService(repository=repository, wikidata_client=wikidata)

    result = service.sync_from_extraction(
        {
            "ingredients": [
                "sugar",
            ]
        }
    )

    assert result == [
        {
            "id": None,
            "name": "sugar",
            "status": "unresolved",
        }
    ]
    assert wikidata.search_calls == ["sugar"]
    assert wikidata.detail_calls == ["Q11002"]


def test_ingredient_sync_returns_unresolved_without_qid() -> None:
    repository = FakeIngredientRepository()
    wikidata = FakeWikidataClient(qid=None)
    service = IngredientSyncService(repository=repository, wikidata_client=wikidata)

    result = service.sync_from_extraction(
        {
            "ingredients": [
                "unknown ingredient",
            ]
        }
    )

    assert result == [
        {
            "id": None,
            "name": "unknown ingredient",
            "status": "unresolved",
        }
    ]
    assert repository.created == []


def test_ingredient_graph_payload_follows_spec() -> None:
    repository = IngredientRepository()

    payload = repository.build_graph_payload(
        {
            "name": "sugar",
        },
        {
            "wikidata_id": "Q10943",
            "name_vi": "đường",
            "name_en": "sugar",
            "description_vi": "chất tạo vị ngọt",
            "description_en": "sweet substance",
            "wikipedia_vi_url": "https://vi.wikipedia.org/wiki/Duong",
            "wikipedia_en_url": "https://en.wikipedia.org/wiki/Sugar",
            "aliases": [
                {
                    "name": "table sugar",
                    "language": "en",
                },
                {
                    "name": "sugar",
                    "language": "en",
                },
            ],
            "categories": [
                {
                    "wikidata_id": "Q2095",
                    "name": "food",
                }
            ],
            "usages": [
                {
                    "wikidata_id": "Q193619",
                    "name": "sweetener",
                }
            ],
        },
    )

    assert payload["ingredient"]["id"] == "INGREDIENT:Q10943"
    assert payload["ingredient"]["wikidata_id"] == "Q10943"
    assert "source_url" not in payload["ingredient"]
    assert payload["source"] == {
        "id": "SOURCE:WIKIDATA",
        "name": "Wikidata",
        "source_url": "https://www.wikidata.org/",
    }
    assert payload["aliases"] == [
        {
            "id": "ALIAS:INGREDIENT:Q10943:1",
            "name": "sugar",
            "normalized_name": "sugar",
            "language": "unknown",
        },
        {
            "id": "ALIAS:INGREDIENT:Q10943:2",
            "name": "đường",
            "normalized_name": "duong",
            "language": "vi",
        },
        {
            "id": "ALIAS:INGREDIENT:Q10943:3",
            "name": "table sugar",
            "normalized_name": "table_sugar",
            "language": "en",
        },
    ]
    assert payload["categories"] == [
        {
            "id": "INGREDIENT:Q2095",
            "wikidata_id": "Q2095",
            "name": "food",
            "normalized_name": "food",
        }
    ]
    assert payload["usages"] == [
        {
            "id": "INGREDIENT_USAGE:Q193619",
            "wikidata_id": "Q193619",
            "name": "sweetener",
            "normalized_name": "sweetener",
        }
    ]


def test_wikidata_search_query_uses_mwapi_entity_search() -> None:
    client = WikidataIngredientClient()

    query = client._search_query("gạo")

    assert "SERVICE wikibase:mwapi" in query
    assert 'wikibase:api "EntitySearch"' in query
    assert 'BIND("gạo" AS ?searchText)' in query
    assert "?descriptionVi" in query
    assert "ORDER BY ASC(?rank)" in query
    assert f"LIMIT {client.settings.search_limit}" in query


def test_wikidata_food_signal_query_checks_candidate_food_context() -> None:
    client = WikidataIngredientClient()

    query = client._food_signal_query(
        [
            "Q34442",
            "Q11002",
        ]
    )

    assert "VALUES ?item { wd:Q34442 wd:Q11002 }" in query
    assert "foodSignalCount" in query
    assert f"wd:{client.settings.food_signal_qids[0]}" in query
    assert "wdt:P31|wdt:P279|wdt:P366" in query


def test_wikidata_search_prefers_food_candidate_over_first_ranked_non_food() -> None:
    client = WikidataIngredientClient()

    candidate = client._select_food_candidate(
        [
            {
                "itemId": {
                    "value": "Q34442",
                },
                "nameVi": {
                    "value": "đường",
                },
                "nameEn": {
                    "value": "road",
                },
                "descriptionVi": {
                    "value": "lộ trình hoặc đường đi trên bộ",
                },
                "descriptionEn": {
                    "value": "wide way leading from one place to another",
                },
                "rank": {
                    "value": "0",
                },
                "foodSignalCount": {
                    "value": "0",
                },
            },
            {
                "itemId": {
                    "value": "Q11002",
                },
                "nameVi": {
                    "value": "đường",
                },
                "nameEn": {
                    "value": "sugar",
                },
                "descriptionVi": {
                    "value": "hợp chất thuộc nhóm cacbohydrat",
                },
                "descriptionEn": {
                    "value": "short-chain carbohydrate",
                },
                "rank": {
                    "value": "3",
                },
                "foodSignalCount": {
                    "value": "3",
                },
            },
        ]
    )

    assert candidate["itemId"]["value"] == "Q11002"


def test_wikidata_search_prefers_exact_food_label_over_broader_rank() -> None:
    client = WikidataIngredientClient()

    candidate = client._select_food_candidate(
        [
            {
                "itemId": {
                    "value": "Q115443",
                },
                "nameVi": {
                    "value": "gạo nếp",
                },
                "nameEn": {
                    "value": "glutinous rice",
                },
                "rank": {
                    "value": "0",
                },
                "foodSignalCount": {
                    "value": "2",
                },
            },
            {
                "itemId": {
                    "value": "Q5090",
                },
                "nameVi": {
                    "value": "gạo",
                },
                "nameEn": {
                    "value": "rice",
                },
                "rank": {
                    "value": "1",
                },
                "foodSignalCount": {
                    "value": "1",
                },
            },
        ],
        "gạo",
    )

    assert candidate["itemId"]["value"] == "Q5090"


def test_wikidata_detail_parser_reads_aggregated_detail_shape() -> None:
    client = WikidataIngredientClient()

    detail = client._parse_detail(
        "Q4739805",
        [
            {
                "nameVi": {
                    "value": "sơ ri",
                },
                "nameEn": {
                    "value": "acerola",
                },
                "descriptionVi": {
                    "value": "loài thực vật",
                },
                "descriptionEn": {
                    "value": "plant species",
                },
                "aliasesVi": {
                    "value": '["kim đồng nam"]',
                },
                "aliasesEn": {
                    "value": '["Barbados cherry"]',
                },
                "categories": {
                    "value": '[{"id":"Q756","labelVi":"thực vật","labelEn":"plant"}]',
                },
                "uses": {
                    "value": '[{"id":"Q2095","labelVi":"","labelEn":"food"}]',
                },
                "wikipediaVi": {
                    "value": "https://vi.wikipedia.org/wiki/S%C6%A1_ri",
                },
                "wikipediaEn": {
                    "value": "https://en.wikipedia.org/wiki/Malpighia_emarginata",
                },
            }
        ],
    )

    assert detail["wikidata_id"] == "Q4739805"
    assert detail["name_vi"] == "sơ ri"
    assert detail["name_en"] == "acerola"
    assert detail["description_vi"] == "loài thực vật"
    assert detail["description_en"] == "plant species"
    assert detail["aliases"] == [
        {
            "name": "kim đồng nam",
            "language": "vi",
        },
        {
            "name": "Barbados cherry",
            "language": "en",
        },
    ]
    assert detail["categories"] == [
        {
            "wikidata_id": "Q756",
            "name": "thực vật",
        }
    ]
    assert detail["usages"] == [
        {
            "wikidata_id": "Q2095",
            "name": "food",
        }
    ]
    assert detail["wikipedia_vi_url"] == "https://vi.wikipedia.org/wiki/S%C6%A1_ri"
    assert detail["wikipedia_en_url"] == "https://en.wikipedia.org/wiki/Malpighia_emarginata"
