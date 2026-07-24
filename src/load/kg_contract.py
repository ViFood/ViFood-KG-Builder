import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.config.settings import KGContractSettings


REQUIRED_SUPPORTED_ENTITIES = ("nutrient", "additive", "ingredient")


@dataclass(frozen=True)
class KGBuilderContract:
    contract_version: str
    release_contracts: dict[str, str]
    supported_entities: dict[str, dict[str, Any]]
    provenance_rules: dict[str, Any]
    raw: dict[str, Any]

    def release_id(self, name: str) -> str:
        value = self.release_contracts.get(name)
        if not value:
            raise ValueError(f"KG contract missing release_contracts.{name}")
        return value

    def entity_contract(self, name: str) -> dict[str, Any]:
        value = self.supported_entities.get(name)
        if not isinstance(value, dict):
            raise ValueError(f"KG contract missing supported_entities.{name}")
        return value


class KGContractLoader:
    def __init__(self, settings: KGContractSettings):
        self.settings = settings

    def load(self) -> KGBuilderContract:
        if not self.settings.path:
            raise ValueError("KG_CONTRACT_PATH is required")

        path = Path(self.settings.path)
        if not path.is_file():
            raise ValueError(f"KG contract file not found: {path}")

        with path.open("r", encoding="utf-8") as f:
            payload = json.load(f)

        return self.from_dict(
            payload,
            expected_version=self.settings.version,
        )

    @staticmethod
    def from_dict(
        payload: dict[str, Any],
        expected_version: str | None = None,
    ) -> KGBuilderContract:
        if not isinstance(payload, dict):
            raise ValueError("KG contract must be a JSON object")

        version = str(payload.get("contract_version") or "").strip()
        if not version:
            raise ValueError("KG contract missing contract_version")

        if expected_version and version != expected_version:
            raise ValueError(
                f"KG contract version mismatch: expected {expected_version}, got {version}"
            )

        release_contracts = payload.get("release_contracts")
        if not isinstance(release_contracts, dict):
            raise ValueError("KG contract missing release_contracts")

        supported_entities = payload.get("supported_entities")
        if not isinstance(supported_entities, dict):
            raise ValueError("KG contract missing supported_entities")

        missing_entities = [
            name
            for name in REQUIRED_SUPPORTED_ENTITIES
            if not isinstance(supported_entities.get(name), dict)
        ]
        if missing_entities:
            raise ValueError(
                "KG contract missing supported entities: "
                + ", ".join(missing_entities)
            )

        for entity_name in REQUIRED_SUPPORTED_ENTITIES:
            entity = supported_entities[entity_name]
            if not entity.get("label"):
                raise ValueError(
                    f"KG contract supported_entities.{entity_name} missing label"
                )
            if not isinstance(entity.get("match_keys"), list):
                raise ValueError(
                    f"KG contract supported_entities.{entity_name} missing match_keys"
                )

        provenance_rules = payload.get("provenance_rules")
        if not isinstance(provenance_rules, dict):
            raise ValueError("KG contract missing provenance_rules")

        return KGBuilderContract(
            contract_version=version,
            release_contracts={
                str(key): str(value)
                for key, value in release_contracts.items()
            },
            supported_entities=supported_entities,
            provenance_rules=provenance_rules,
            raw=payload,
        )
