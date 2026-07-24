import copy
import json

import pytest

from src.config.settings import KGContractSettings
from src.load.kg_contract import KGContractLoader


VALID_CONTRACT = {
    "contract_version": "2026-07-13.1",
    "release_contracts": {
        "nutrient": "nutrients_vietnam_infoods_v0.2.0",
        "additive": "vietnam_additive_master_v0.1.2",
        "additive_permissions": "vietnam_additive_permissions_2a_v0.1.0",
    },
    "supported_entities": {
        "nutrient": {
            "label": "Nutrient",
            "match_keys": ["external_code"],
        },
        "additive": {
            "label": "Additive",
            "match_keys": ["normalized(ins)"],
        },
        "ingredient": {
            "label": "Ingredient",
            "match_keys": ["normalized(name)"],
        },
    },
    "provenance_rules": {
        "entity_source_relationship": "SUPPORTED_BY",
    },
}


def test_loads_valid_contract_from_file(tmp_path) -> None:
    path = tmp_path / "kg_schema_contract.json"
    path.write_text(
        json.dumps(VALID_CONTRACT),
        encoding="utf-8",
    )

    contract = KGContractLoader(
        KGContractSettings(
            path=str(path),
            version="2026-07-13.1",
        )
    ).load()

    assert contract.contract_version == "2026-07-13.1"
    assert contract.release_id("nutrient") == "nutrients_vietnam_infoods_v0.2.0"
    assert contract.entity_contract("additive")["label"] == "Additive"


def test_rejects_missing_contract_file(tmp_path) -> None:
    with pytest.raises(ValueError, match="file not found"):
        KGContractLoader(
            KGContractSettings(
                path=str(tmp_path / "missing.json"),
                version="2026-07-13.1",
            )
        ).load()


def test_rejects_wrong_contract_version() -> None:
    with pytest.raises(ValueError, match="version mismatch"):
        KGContractLoader.from_dict(
            VALID_CONTRACT,
            expected_version="2026-07-14.1",
        )


def test_rejects_missing_supported_entity() -> None:
    payload = copy.deepcopy(VALID_CONTRACT)
    payload["supported_entities"].pop("ingredient")

    with pytest.raises(ValueError, match="missing supported entities: ingredient"):
        KGContractLoader.from_dict(
            payload,
            expected_version="2026-07-13.1",
        )


def test_rejects_supported_entity_without_match_keys() -> None:
    payload = copy.deepcopy(VALID_CONTRACT)
    payload["supported_entities"]["nutrient"].pop("match_keys")

    with pytest.raises(ValueError, match="nutrient missing match_keys"):
        KGContractLoader.from_dict(
            payload,
            expected_version="2026-07-13.1",
        )
