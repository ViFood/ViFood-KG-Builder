from typing import Any


class SemanticContextBuilder:
    def build(self, raw_item: dict[str, Any], entity_type: str) -> dict[str, Any]:
        normalized_type = entity_type.lower()
        entity = raw_item.get("entity") or {}
        relationships = raw_item.get("relationships") or {}
        display_name = self._display_name(entity)
        secondary_name = self._secondary_name(entity, display_name)
        identifier_text = self._identifier_text(entity, normalized_type)
        evidence = self._evidence(entity, relationships)
        return {
            "entity_id": str(entity.get("id") or entity.get("external_code") or entity.get("code") or ""),
            "entity_type": normalized_type,
            "display_name": display_name,
            "secondary_name": secondary_name,
            "identifier_text": identifier_text,
            "summary": self._summary(entity, normalized_type, display_name),
            "facts": self._facts(entity, normalized_type),
            "related": relationships,
            "evidence": evidence,
            "source_summary": self._source_summary(evidence, relationships),
        }

    @staticmethod
    def _display_name(entity: dict[str, Any]) -> str:
        return str(entity.get("name_vi") or entity.get("vi_name") or entity.get("name") or entity.get("id") or "")

    @staticmethod
    def _secondary_name(entity: dict[str, Any], display_name: str) -> str:
        name = str(entity.get("name") or entity.get("english_name") or "")
        if name and name != display_name:
            return name
        return ""

    @staticmethod
    def _identifier_text(entity: dict[str, Any], entity_type: str) -> str:
        if entity_type == "additive" and entity.get("ins"):
            return f"INS {entity['ins']}"
        if entity_type == "ingredient":
            for key in ("external_code", "chebi_id", "foodon_id"):
                if entity.get(key):
                    return str(entity[key])
        if entity_type == "nutrient" and entity.get("external_code"):
            return str(entity["external_code"])
        return str(entity.get("code") or "")

    @staticmethod
    def _summary(entity: dict[str, Any], entity_type: str, display_name: str) -> str:
        for key in ("summary", "description", "definition", "note"):
            if entity.get(key):
                return str(entity[key]).strip()
        type_text = {
            "ingredient": "nguyên liệu hoặc thành phần thực phẩm",
            "additive": "phụ gia thực phẩm",
            "nutrient": "chất dinh dưỡng",
        }.get(entity_type, "thực thể thực phẩm")
        return f"{display_name} là một {type_text} được ghi nhận trong ViFood-KC."

    @staticmethod
    def _facts(entity: dict[str, Any], entity_type: str) -> list[dict[str, str]]:
        field_labels = {
            "external_code": "Mã ngoài",
            "ins": "Mã INS",
            "default_unit": "Đơn vị mặc định",
            "chebi_id": "ChEBI",
            "foodon_id": "FoodOn",
            "source": "Nguồn",
            "reviewed_at": "Ngày rà soát",
        }
        priority = {
            "ingredient": ("external_code", "chebi_id", "foodon_id", "reviewed_at"),
            "additive": ("ins", "external_code", "reviewed_at"),
            "nutrient": ("external_code", "default_unit", "reviewed_at"),
        }.get(entity_type, ())
        facts = []
        for key in priority:
            value = entity.get(key)
            if value not in (None, ""):
                facts.append({"label": field_labels.get(key, key), "value": str(value)})
        return facts

    @staticmethod
    def _evidence(entity: dict[str, Any], relationships: dict[str, Any]) -> dict[str, Any]:
        sources = relationships.get("sources") or []
        regulations = relationships.get("regulations") or []
        primary_source = sources[0] if sources else {}
        return {
            "source": entity.get("source") or primary_source.get("title") or primary_source.get("name"),
            "source_id": primary_source.get("id"),
            "source_url": entity.get("source_url") or primary_source.get("url"),
            "reviewed_at": entity.get("reviewed_at") or primary_source.get("reviewed_at"),
            "raw_page_number": entity.get("raw_page_number") or primary_source.get("raw_page_number"),
            "raw_record_number": entity.get("raw_record_number") or primary_source.get("raw_record_number"),
            "sources": sources,
            "regulations": regulations,
        }

    @staticmethod
    def _source_summary(evidence: dict[str, Any], relationships: dict[str, Any]) -> str:
        source_count = len(relationships.get("sources") or [])
        regulation_count = len(relationships.get("regulations") or [])
        parts = []
        if source_count:
            parts.append(f"{source_count} nguồn dữ liệu")
        if regulation_count:
            parts.append(f"{regulation_count} mục quy định")
        if parts:
            return " và ".join(parts)
        if evidence.get("source"):
            return str(evidence["source"])
        return "chưa có nguồn hỗ trợ riêng được gắn trực tiếp"
