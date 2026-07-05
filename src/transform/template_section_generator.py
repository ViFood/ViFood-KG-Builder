from typing import Any


SECTION_TITLES = {
    "overview": "Tổng quan",
    "classification_and_role": "Phân loại và vai trò",
    "common_foods": "Thường gặp trong thực phẩm",
    "health_note": "Điều cần lưu ý cho sức khỏe",
    "source_and_regulation": "Nguồn và quy định",
}

SECTION_ORDER = tuple(SECTION_TITLES)


class TemplateSectionGenerator:
    def generate(self, context: dict[str, Any], source_hash: str) -> list[dict[str, Any]]:
        section_specs = [
            ("overview", self._overview(context)),
            ("classification_and_role", self._classification_and_role(context)),
            ("common_foods", self._common_foods(context)),
            ("health_note", self._health_note(context)),
            ("source_and_regulation", self._source_and_regulation(context)),
        ]

        sections: list[dict[str, Any]] = []
        for section_type, content in section_specs:
            if not content:
                continue
            sections.append(
                {
                    "id": f"WIKI:{context['entity_id']}:{section_type}",
                    "title": SECTION_TITLES[section_type],
                    "content": content,
                    "section_type": section_type,
                    "order": len(sections) + 1,
                    "status": "draft",
                    "source_hash": source_hash,
                    "generated_by": "template",
                }
            )
        return sections

    def _overview(self, context: dict[str, Any]) -> str:
        entity_type = context.get("entity_type")
        if entity_type == "ingredient":
            return self._ingredient_overview(context)
        if entity_type == "additive":
            return self._additive_overview(context)
        if entity_type == "nutrient":
            return self._nutrient_overview(context)
        return self._generic_overview(context)

    def _classification_and_role(self, context: dict[str, Any]) -> str:
        entity_type = context.get("entity_type")
        if entity_type == "ingredient":
            return self._ingredient_classification_and_role(context)
        if entity_type == "additive":
            return self._additive_classification_and_role(context)
        if entity_type == "nutrient":
            return self._nutrient_classification_and_role(context)
        return self._generic_classification_and_role(context)

    def _common_foods(self, context: dict[str, Any]) -> str:
        entity_type = context.get("entity_type")
        if entity_type == "ingredient":
            return self._ingredient_common_foods(context)
        if entity_type == "additive":
            return self._additive_common_foods(context)
        if entity_type == "nutrient":
            return self._nutrient_common_foods(context)
        return self._generic_common_foods(context)

    def _health_note(self, context: dict[str, Any]) -> str:
        entity_type = context.get("entity_type")
        if entity_type == "ingredient":
            return self._ingredient_health_note(context)
        if entity_type == "additive":
            return self._additive_health_note(context)
        if entity_type == "nutrient":
            return self._nutrient_health_note(context)
        return self._generic_health_note(context)

    def _source_and_regulation(self, context: dict[str, Any]) -> str:
        entity_type = context.get("entity_type")
        if entity_type == "additive":
            return self._additive_source_and_regulation(context)
        if entity_type == "nutrient":
            return self._nutrient_source_and_regulation(context)
        if entity_type == "ingredient":
            return self._ingredient_source_and_regulation(context)
        return self._generic_source_and_regulation(context)

    def _ingredient_overview(self, context: dict[str, Any]) -> str:
        name = self._display_name(context)
        parts = [f"{name} là một nguyên liệu hoặc thành phần có thể xuất hiện trong thực phẩm."]
        parts.extend(self._name_parts(context))
        summary = self._overview_summary(context)
        if summary:
            parts.append(summary)
        return " ".join(parts)

    def _additive_overview(self, context: dict[str, Any]) -> str:
        name = self._display_name(context)
        parts = [f"{name} là một phụ gia thực phẩm."]
        parts.extend(self._name_parts(context))
        summary = self._overview_summary(context)
        if summary:
            parts.append(summary)
        return " ".join(parts)

    def _nutrient_overview(self, context: dict[str, Any]) -> str:
        name = self._display_name(context)
        parts = [f"{name} là một chất dinh dưỡng có thể được nhắc đến trong thông tin dinh dưỡng của thực phẩm."]
        parts.extend(self._name_parts(context))
        summary = self._overview_summary(context)
        if summary:
            parts.append(summary)
        return " ".join(parts)

    def _generic_overview(self, context: dict[str, Any]) -> str:
        name = self._display_name(context)
        parts = [f"{name} là một thông tin liên quan đến thực phẩm."]
        parts.extend(self._name_parts(context))
        summary = self._overview_summary(context)
        if summary:
            parts.append(summary)
        return " ".join(parts)

    def _ingredient_classification_and_role(self, context: dict[str, Any]) -> str:
        name = self._display_name(context)
        groups = self._names(context, "groups")
        parents = self._names(context, "parent_ingredients")
        derived_from = self._names(context, "derived_from")
        nutrients = self._names(context, "nutrients", limit=8)
        parts = []

        if groups:
            parts.append(f"{name} thuộc hoặc liên quan đến nhóm {self._join(groups)}.")
        if parents:
            parts.append(f"Có thể hiểu {name} là một dạng của {self._join(parents)}.")
        if derived_from:
            parts.append(f"Nguyên liệu hoặc nguồn gốc liên quan gồm {self._join(derived_from)}.")
        if nutrients:
            parts.append(f"Về vai trò dinh dưỡng, {name} có liên quan đến {self._join(nutrients)}.")
        return " ".join(parts)

    def _additive_classification_and_role(self, context: dict[str, Any]) -> str:
        name = self._display_name(context)
        functions = self._names(context, "functions")
        groups = self._names(context, "groups")
        parts = []

        if groups:
            parts.append(f"{name} thuộc hoặc liên quan đến nhóm {self._join(groups)}.")
        if functions:
            parts.append(f"Trong thực phẩm, phụ gia này có vai trò {self._join(functions)}.")
        return " ".join(parts)

    def _nutrient_classification_and_role(self, context: dict[str, Any]) -> str:
        name = self._display_name(context)
        groups = self._names(context, "groups")
        ingredients = self._names(context, "ingredients", limit=8)
        unit = self._fact_value(context, "Đơn vị mặc định")
        parts = []

        if groups:
            parts.append(f"{name} thuộc hoặc liên quan đến nhóm chất dinh dưỡng {self._join(groups)}.")
        if unit:
            parts.append(f"Khi đọc nhãn, chất này thường được ghi theo đơn vị {unit}.")
        if ingredients:
            parts.append(f"Một số nguyên liệu có liên quan đến chất dinh dưỡng này gồm {self._join(ingredients)}.")
        return " ".join(parts)

    def _generic_classification_and_role(self, context: dict[str, Any]) -> str:
        name = self._display_name(context)
        groups = self._names(context, "groups")
        functions = self._names(context, "functions")
        parts = []
        if groups:
            parts.append(f"{name} liên quan đến nhóm {self._join(groups)}.")
        if functions:
            parts.append(f"Vai trò được ghi nhận gồm {self._join(functions)}.")
        return " ".join(parts)

    def _ingredient_common_foods(self, context: dict[str, Any]) -> str:
        name = self._display_name(context)
        foods = self._food_names(context)
        if not foods:
            return ""
        return f"Người dùng có thể gặp {name} trong các nhóm hoặc loại thực phẩm như {self._join(foods)}."

    def _additive_common_foods(self, context: dict[str, Any]) -> str:
        name = self._display_name(context)
        permitted_in = self._names(context, "permitted_in", limit=10)
        food_categories = self._names(context, "food_categories", limit=10)
        common_foods = self._names(context, "common_foods", limit=10)
        foods = self._unique(permitted_in + food_categories + common_foods)
        if not foods:
            return ""
        return f"Theo dữ liệu hiện có, {name} có thể xuất hiện trong các nhóm thực phẩm như {self._join(foods)}."

    def _nutrient_common_foods(self, context: dict[str, Any]) -> str:
        name = self._display_name(context)
        foods = self._food_names(context)
        ingredients = self._names(context, "ingredients", limit=8)
        items = self._unique(foods + ingredients)
        if not items:
            return ""
        return f"{name} có thể được nhắc đến cùng các nguyên liệu hoặc nhóm thực phẩm như {self._join(items)}."

    def _generic_common_foods(self, context: dict[str, Any]) -> str:
        name = self._display_name(context)
        foods = self._food_names(context)
        if not foods:
            return ""
        return f"{name} liên quan đến các nhóm thực phẩm như {self._join(foods)}."

    def _ingredient_health_note(self, context: dict[str, Any]) -> str:
        name = self._display_name(context)
        allergens = self._names(context, "allergens", limit=8)
        nutrients = self._names(context, "nutrients", limit=8)
        health_effects = self._names(context, "health_effects", limit=8)
        warnings = self._names(context, "warnings", limit=8)
        parts = []

        if allergens:
            parts.append(f"Người có dị ứng cần chú ý vì {name} có liên quan đến {self._join(allergens)}.")
        if nutrients:
            parts.append(f"Về mặt dinh dưỡng, nguyên liệu này có liên quan đến {self._join(nutrients)}.")
        if health_effects:
            parts.append(f"Thông tin sức khỏe liên quan gồm {self._join(health_effects)}.")
        if warnings:
            parts.append(f"Lưu ý được ghi nhận: {self._join(warnings)}.")
        return " ".join(parts)

    def _additive_health_note(self, context: dict[str, Any]) -> str:
        name = self._display_name(context)
        allergens = self._names(context, "allergens", limit=8)
        health_effects = self._names(context, "health_effects", limit=8)
        warnings = self._names(context, "warnings", limit=8)
        health_claims = self._names(context, "health_claims", limit=8)
        parts = []

        if allergens:
            parts.append(f"Thông tin dị ứng liên quan đến {name}: {self._join(allergens)}.")
        if health_effects:
            parts.append(f"Tác động sức khỏe được ghi nhận gồm {self._join(health_effects)}.")
        if health_claims:
            parts.append(f"Thông tin sức khỏe liên quan gồm {self._join(health_claims)}.")
        if warnings:
            parts.append(f"Lưu ý được ghi nhận: {self._join(warnings)}.")
        return " ".join(parts)

    def _nutrient_health_note(self, context: dict[str, Any]) -> str:
        name = self._display_name(context)
        health_claims = self._names(context, "health_claims", limit=8)
        health_effects = self._names(context, "health_effects", limit=8)
        warnings = self._names(context, "warnings", limit=8)
        parts = []

        if health_claims:
            parts.append(f"{name} có liên quan đến các thông tin sức khỏe như {self._join(health_claims)}.")
        if health_effects:
            parts.append(f"Tác động sức khỏe được ghi nhận gồm {self._join(health_effects)}.")
        if warnings:
            parts.append(f"Lưu ý được ghi nhận: {self._join(warnings)}.")
        return " ".join(parts)

    def _generic_health_note(self, context: dict[str, Any]) -> str:
        health_items = self._health_names(context)
        if not health_items:
            return ""
        name = self._display_name(context)
        return f"Thông tin sức khỏe liên quan đến {name} gồm {self._join(health_items)}."

    def _ingredient_source_and_regulation(self, context: dict[str, Any]) -> str:
        return self._source_and_regulation_text(context, mention_regulation=False)

    def _additive_source_and_regulation(self, context: dict[str, Any]) -> str:
        return self._source_and_regulation_text(context, mention_regulation=True)

    def _nutrient_source_and_regulation(self, context: dict[str, Any]) -> str:
        return self._source_and_regulation_text(context, mention_regulation=True)

    def _generic_source_and_regulation(self, context: dict[str, Any]) -> str:
        return self._source_and_regulation_text(context, mention_regulation=True)

    def _source_and_regulation_text(self, context: dict[str, Any], mention_regulation: bool) -> str:
        evidence = context.get("evidence") or {}
        sources = self._names(context, "sources", limit=5)
        regulations = self._names(context, "regulations", limit=5)
        source_summary = str(context.get("source_summary") or "").strip()
        parts = []

        if sources:
            parts.append(f"Thông tin này được tổng hợp từ {self._join(sources)}.")
        elif source_summary:
            parts.append(f"Thông tin này được tổng hợp từ {source_summary}.")

        if mention_regulation and regulations:
            parts.append(f"Quy định liên quan gồm {self._join(regulations)}.")

        reviewed_at = evidence.get("reviewed_at")
        source_url = evidence.get("source_url")
        page = evidence.get("raw_page_number")
        record = evidence.get("raw_record_number")

        if reviewed_at:
            parts.append(f"Ngày rà soát dữ liệu: {reviewed_at}.")
        if page:
            parts.append(f"Trang nguồn: {page}.")
        if record:
            parts.append(f"Số bản ghi nguồn: {record}.")
        if source_url:
            parts.append(f"Đường dẫn nguồn: {source_url}.")
        return " ".join(parts)

    def _name_parts(self, context: dict[str, Any]) -> list[str]:
        parts = []
        secondary_name = str(context.get("secondary_name") or "").strip()
        identifier = str(context.get("identifier_text") or "").strip()
        aliases = self._names(context, "aliases", limit=5)

        if secondary_name:
            parts.append(f"Tên khác hoặc tên tiếng Anh thường gặp là {secondary_name}.")
        if identifier:
            parts.append(f"Trên nhãn hoặc tài liệu tham khảo, chất này có thể đi kèm mã {identifier}.")
        if aliases:
            parts.append(f"Một số cách gọi khác gồm {self._join(aliases)}.")
        return parts

    def _food_names(self, context: dict[str, Any]) -> list[str]:
        return self._unique(
            self._names(context, "common_foods", limit=10)
            + self._names(context, "food_categories", limit=10)
            + self._names(context, "permitted_in", limit=10)
        )

    def _health_names(self, context: dict[str, Any]) -> list[str]:
        return self._unique(
            self._names(context, "allergens", limit=8)
            + self._names(context, "health_claims", limit=8)
            + self._names(context, "health_effects", limit=8)
            + self._names(context, "warnings", limit=8)
        )

    def _names(self, context: dict[str, Any], key: str, limit: int = 6) -> list[str]:
        related = context.get("related") or {}
        values = related.get(key) or []
        if not isinstance(values, list):
            return []

        names = []
        for value in values:
            if not isinstance(value, dict):
                continue
            name = self._node_name(value)
            if name and name not in names:
                names.append(name)
            if len(names) >= limit:
                break
        return names

    @staticmethod
    def _node_name(node: dict[str, Any]) -> str:
        for key in ("name_vi", "vi_name", "title", "name", "code", "ins", "e_number", "external_code", "id"):
            value = node.get(key)
            if value not in (None, ""):
                return str(value)
        return ""

    @staticmethod
    def _display_name(context: dict[str, Any]) -> str:
        return str(context.get("display_name") or context.get("entity_id") or "Thông tin này")

    @staticmethod
    def _summary(context: dict[str, Any]) -> str:
        summary = str(context.get("summary") or "").strip()
        blocked = (
            "được ghi nhận trong ViFood-KC.",
            "ViFood-KC",
            "graph",
            "node",
            "relationship",
        )
        if not summary or any(term.lower() in summary.lower() for term in blocked):
            return ""
        return summary

    @classmethod
    def _overview_summary(cls, context: dict[str, Any]) -> str:
        summary = cls._summary(context)
        if not summary:
            return ""

        blocked_markers = (
            "dùng để",
            "được dùng",
            "vai trò",
            "chức năng",
            "thường gặp",
            "xuất hiện trong",
            "được phép",
            "quy định",
            "nguồn",
            "sức khỏe",
            "dị ứng",
            "cảnh báo",
        )
        sentences = [part.strip() for part in summary.split(".") if part.strip()]
        overview_sentences = [
            sentence
            for sentence in sentences
            if not any(marker in sentence.lower() for marker in blocked_markers)
        ]
        if not overview_sentences:
            return ""
        return ". ".join(overview_sentences) + "."

    @staticmethod
    def _fact_value(context: dict[str, Any], label: str) -> str:
        for fact in context.get("facts") or []:
            if not isinstance(fact, dict):
                continue
            if fact.get("label") == label:
                return str(fact.get("value") or "")
        return ""

    @staticmethod
    def _join(values: list[str]) -> str:
        if len(values) <= 1:
            return values[0] if values else ""
        return ", ".join(values[:-1]) + f" và {values[-1]}"

    @staticmethod
    def _unique(values: list[str]) -> list[str]:
        unique_values = []
        for value in values:
            if value and value not in unique_values:
                unique_values.append(value)
        return unique_values
