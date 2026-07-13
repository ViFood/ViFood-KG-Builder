from src.load.ingredient_repository import IngredientRepository
from src.load.ingredient_sync_service import IngredientSyncService


class FakeIngredientRepository:
    def __init__(self, existing=None):
        self.is_configured = True
        self.existing = existing
        self.created = []

    def match_existing(self, ingredient):
        return self.existing

    def sync_from_detail(self, ingredient, detail):
        self.created.append((ingredient, detail))
        return {
            "id": f"INGREDIENT:{detail['wikidata_id']}",
            "name": ingredient["name"],
            "status": "created",
        }


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
