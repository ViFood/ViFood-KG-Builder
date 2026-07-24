import re

from src.load.runtime_neo4j_service import Neo4jService


class AdditiveSyncService:
    def __init__(self):
        self.neo4j_service = Neo4jService()

    def sync_from_extraction(self, extraction_result: dict) -> list[dict]:
        additives = self._normalize_additives(
            extraction_result.get("additives")
            or extraction_result.get("additive")
        )

        if not additives:
            return []

        if not self.neo4j_service.is_configured:
            return additives

        return [
            self.neo4j_service.sync_additive(additive)
            for additive in additives
        ]

    def _normalize_additives(self, additive) -> list[dict]:
        if isinstance(additive, list):
            additives = []

            for item in additive:
                additives.extend(
                    self._normalize_additive_item(item)
                )

            return [
                item
                for item in additives
                if item["name"] or item["ins"]
            ]

        if isinstance(additive, dict):
            return self._normalize_additive_item(additive)

        if isinstance(additive, str):
            return self._normalize_additive_item(additive)

        return []

    def _normalize_additive_item(self, item) -> list[dict]:
        if isinstance(item, dict):
            name = str(
                item.get("name")
                or item.get("label")
                or item.get("additives")
                or item.get("additive")
                or ""
            ).strip()
            ins = self._normalize_ins(
                item.get("ins")
                or item.get("code")
                or item.get("external_code")
            )

            if not ins:
                ins_codes = self._extract_ins_codes(name)

                return [
                    self._build_additive(name, code, item)
                    for code in ins_codes
                ] or [
                    self._build_additive(name, None, item)
                ]

            return [
                self._build_additive(name, ins, item)
            ]

        name = str(item or "").strip()

        return [
            self._build_additive(name, code, {})
            for code in self._extract_ins_codes(name)
        ] or [
            self._build_additive(name, None, {})
        ]

    def _build_additive(
        self,
        name: str,
        ins: str | None,
        source: dict
    ) -> dict:
        return {
            "name": name,
            "name_vi": source.get("name_vi") or name,
            "ins": ins,
            "raw_page_number": source.get("raw_page_number"),
            "raw_record_number": source.get("raw_record_number")
        }

    def _extract_ins_codes(self, value: str) -> list[str]:
        if not value:
            return []

        prefixed_codes = re.findall(
            r"\b(?:INS|E)\s*[-:]?\s*([0-9]{3,4}[a-zA-Z]?(?:\([ivxIVX]+\))?)",
            value,
            flags=re.IGNORECASE
        )

        if prefixed_codes:
            return [
                self._normalize_ins(code)
                for code in prefixed_codes
                if self._normalize_ins(code)
            ]

        loose_codes = re.findall(
            r"(?<![0-9])([0-9]{3,4}[a-zA-Z]?(?:\([ivxIVX]+\))?)(?![0-9])",
            value
        )

        return [
            self._normalize_ins(code)
            for code in loose_codes
            if self._normalize_ins(code)
        ]

    def _normalize_ins(self, value) -> str | None:
        if value in (None, ""):
            return None

        normalized = str(value).strip().upper()
        normalized = normalized.removeprefix("INS").strip()
        normalized = normalized.removeprefix("E").strip()
        normalized = re.sub(r"[^0-9A-Z()]+", "", normalized)

        return normalized or None
