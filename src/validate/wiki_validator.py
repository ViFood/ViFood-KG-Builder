import json
from pathlib import Path
from typing import Any

from src.validate.required_field_validator import RequiredFieldValidator
from src.validate.source_validator import SourceValidator


class ValidationError(Exception):
    pass


class WikiValidator:
    def __init__(self) -> None:
        self.required = RequiredFieldValidator()
        self.source = SourceValidator()

    def validate_file(self, path: str | Path) -> list[str]:
        with Path(path).open("r", encoding="utf-8") as f:
            payload = json.load(f)
        return self.validate_payload(payload)

    def assert_valid_file(self, path: str | Path) -> None:
        errors = self.validate_file(path)
        if errors:
            raise ValidationError("\n".join(errors))

    def validate_payload(self, payload: Any) -> list[str]:
        if not isinstance(payload, dict) or not isinstance(payload.get("items"), list):
            return ["Root JSON must be an object with an items list."]
        errors: list[str] = []
        for item in payload["items"]:
            errors.extend(self.validate_item(item))
        return errors

    def validate_item(self, item: dict[str, Any]) -> list[str]:
        entity_id = item.get("entity_id", "<missing entity_id>")
        errors: list[str] = []
        errors.extend(self.required.validate(item))
        errors.extend(self.source.validate(item))
        if not item.get("source_hash"):
            errors.append(f"{entity_id}: source_hash is required.")

        entity_type = item.get("entity_type")
        facts = {fact.get("label"): fact.get("value") for fact in item.get("facts") or []}
        if entity_type == "additive" and not self._has_value(item, "ins", "Mã INS", facts):
            errors.append(f"{entity_id}: additive requires ins.")
        if entity_type == "nutrient":
            if not self._has_value(item, "external_code", "Mã ngoài", facts):
                errors.append(f"{entity_id}: nutrient requires external_code.")
            if not self._has_value(item, "default_unit", "Đơn vị mặc định", facts):
                errors.append(f"{entity_id}: nutrient requires default_unit.")
        if entity_type not in ("additive", "nutrient"):
            errors.append(f"{entity_id}: entity_type must be additive or nutrient.")
        return errors

    @staticmethod
    def _has_value(item: dict[str, Any], evidence_key: str, fact_label: str, facts: dict[str, Any]) -> bool:
        if item.get(evidence_key):
            return True
        if facts.get(fact_label):
            return True
        profile = item.get("wiki_profile") or {}
        if evidence_key == "ins" and "INS " in str(profile.get("subtitle") or ""):
            return True
        return False
