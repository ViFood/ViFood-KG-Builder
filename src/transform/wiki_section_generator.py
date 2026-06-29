from typing import Any


class WikiSectionGenerator:
    def generate(self, context: dict[str, Any]) -> list[dict[str, Any]]:
        entity_type = context["entity_type"]
        if entity_type == "ingredient":
            specs = [
                ("overview", "Tổng quan", self._has_overview_data, self._ingredient_overview),
                ("role", "Vai trò trong thực phẩm", lambda ctx: self._has_related(ctx, "nutrients"), self._ingredient_role),
                ("classification", "Phân loại và nguồn gốc", lambda ctx: self._has_any_related(ctx, ("groups", "parent_ingredients", "derived_from")), self._ingredient_classification),
                ("health", "Liên quan đến dinh dưỡng hoặc dị nguyên", lambda ctx: self._has_any_related(ctx, ("nutrients", "allergens")), self._ingredient_health),
                ("evidence", "Nguồn dữ liệu", self._has_evidence_data, self._evidence),
            ]
        elif entity_type == "additive":
            specs = [
                ("overview", "Tổng quan", self._has_overview_data, self._additive_overview),
                ("role", "Vai trò trong thực phẩm", lambda ctx: self._has_related(ctx, "functions"), self._additive_role),
                ("usage_scope", "Phạm vi sử dụng", lambda ctx: self._has_related(ctx, "permitted_in"), self._additive_usage_scope),
                ("regulation", "Quy định và nguồn dữ liệu", lambda ctx: self._has_related(ctx, "regulations") or self._has_evidence_data(ctx), self._additive_regulation),
                ("interpretation", "Lưu ý khi diễn giải", self._has_any_context_data, self._interpretation),
            ]
        elif entity_type == "nutrient":
            specs = [
                ("overview", "Tổng quan", self._has_overview_data, self._nutrient_overview),
                ("nutrition", "Ý nghĩa dinh dưỡng", lambda ctx: self._has_related(ctx, "ingredients"), self._nutrient_meaning),
                ("unit", "Đơn vị và chuẩn dữ liệu", lambda ctx: bool(self._fact_value(ctx, "Đơn vị mặc định") or ctx.get("identifier_text")), self._nutrient_unit),
                ("labeling", "Ghi nhãn tại Việt Nam", self._has_evidence_data, self._nutrient_labeling),
                ("claim", "Claim sức khỏe liên quan", lambda ctx: self._has_related(ctx, "health_claims"), self._nutrient_claim),
                ("evidence", "Nguồn dữ liệu", self._has_evidence_data, self._evidence),
            ]
        else:
            specs = [("overview", "Tổng quan", self._has_overview_data, self._generic_overview)]

        sections: list[dict[str, Any]] = []
        for section_type, title, predicate, builder in specs:
            if not predicate(context):
                continue
            sections.append({
                "id": f"WIKI:{context['entity_id']}:{section_type}",
                "title": title,
                "content": builder(context),
                "section_type": section_type,
                "order": len(sections) + 1,
                "status": "draft",
                "evidence": self._section_evidence(context, section_type),
            })
        return sections

    def _ingredient_overview(self, ctx: dict[str, Any]) -> str:
        return (
            f"{ctx['display_name']} được ghi nhận trong ViFood-KC như một nguyên liệu hoặc "
            f"thành phần thực phẩm. {ctx['summary']} Thông tin này nên được đọc như dữ liệu "
            "tri thức đã biên mục, không phải kết luận tuyệt đối về lợi ích hay rủi ro."
        )

    def _ingredient_role(self, ctx: dict[str, Any]) -> str:
        nutrients = self._names(ctx, "nutrients")
        return (
            f"Trong bối cảnh thực phẩm, {ctx['display_name']} nên được hiểu theo công thức, "
            f"khẩu phần và cách chế biến cụ thể. Dữ liệu hiện liên kết nguyên liệu này với "
            f"các chất dinh dưỡng như {nutrients}. Nội dung không thay thế đánh giá "
            "dinh dưỡng cho từng sản phẩm hoặc từng nhóm người dùng."
        )

    def _ingredient_classification(self, ctx: dict[str, Any]) -> str:
        groups = self._names(ctx, "groups")
        parents = self._names(ctx, "parent_ingredients")
        derived = self._names(ctx, "derived_from")
        parts = []
        if groups:
            parts.append(f"nhóm nguyên liệu: {groups}")
        if parents:
            parts.append(f"quan hệ phân cấp: {parents}")
        if derived:
            parts.append(f"nguồn gốc hoặc dẫn xuất: {derived}")
        detail = "; ".join(parts)
        return f"Phần phân loại của {ctx['display_name']} dựa trên {detail}. Các liên kết này giúp người đọc hiểu vị trí của nguyên liệu trong đồ thị tri thức."

    def _ingredient_health(self, ctx: dict[str, Any]) -> str:
        nutrients = self._names(ctx, "nutrients")
        allergens = self._names(ctx, "allergens")
        nutrient_text = f"Dữ liệu dinh dưỡng có nhắc tới {nutrients}." if nutrients else ""
        allergen_text = f"Dữ liệu dị nguyên có nhắc tới {allergens}." if allergens else ""
        return f"{nutrient_text} {allergen_text} Việc thiếu dữ liệu không có nghĩa là không có rủi ro; người dùng vẫn cần đọc nhãn và nguồn áp dụng."

    def _additive_overview(self, ctx: dict[str, Any]) -> str:
        identifier = f" ({ctx['identifier_text']})" if ctx.get("identifier_text") else ""
        return (
            f"{ctx['display_name']}{identifier} được ghi nhận như một phụ gia thực phẩm trong "
            f"ViFood-KC. {ctx['summary']} Mô tả này nhằm hỗ trợ tra cứu tri thức và không tự "
            "động kết luận phụ gia là an toàn hoặc nguy hiểm trong mọi điều kiện sử dụng."
        )

    def _additive_role(self, ctx: dict[str, Any]) -> str:
        functions = self._names(ctx, "functions")
        return f"Vai trò của {ctx['display_name']} cần được hiểu theo mục đích công nghệ trong thực phẩm. Các chức năng được ghi nhận gồm {functions}."

    def _additive_usage_scope(self, ctx: dict[str, Any]) -> str:
        categories = self._names(ctx, "permitted_in")
        return f"Phạm vi sử dụng đang được liên kết với các nhóm thực phẩm như {categories}. Người đọc cần đối chiếu thêm điều kiện, mức dùng và phạm vi áp dụng trong nguồn quy định."

    def _additive_regulation(self, ctx: dict[str, Any]) -> str:
        regulations = self._names(ctx, "regulations")
        source_text = ctx.get("source_summary") or "nguồn dữ liệu chưa rõ"
        if regulations:
            return f"Các quy định liên quan trong đồ thị gồm {regulations}. Hồ sơ này dựa trên {source_text}; khi dùng cần kiểm tra phiên bản và phạm vi pháp lý của từng nguồn."
        return f"Hồ sơ này dựa trên {source_text}. Khi dùng cần kiểm tra phiên bản, phạm vi pháp lý và điều kiện áp dụng trong nguồn."

    def _interpretation(self, ctx: dict[str, Any]) -> str:
        return (
            f"Khi diễn giải {ctx['display_name']}, cần xem xét liều lượng, nhóm thực phẩm, "
            "đối tượng sử dụng và văn bản nguồn. Nội dung wiki chỉ tóm tắt tri thức trong "
            "graph, không thay thế tư vấn y tế, pháp lý hoặc đánh giá rủi ro chuyên môn."
        )

    def _nutrient_overview(self, ctx: dict[str, Any]) -> str:
        return f"{ctx['display_name']} được ghi nhận như một chất dinh dưỡng trong ViFood-KC. {ctx['summary']} Hồ sơ này trình bày dữ liệu theo hướng tra cứu cho người dùng phổ thông."

    def _nutrient_meaning(self, ctx: dict[str, Any]) -> str:
        ingredients = self._names(ctx, "ingredients")
        return f"Ý nghĩa dinh dưỡng của {ctx['display_name']} cần được đặt trong khẩu phần, đơn vị đo và nhu cầu cá nhân. Trong đồ thị, chất này xuất hiện ở các nguyên liệu như {ingredients}."

    def _nutrient_unit(self, ctx: dict[str, Any]) -> str:
        unit = self._fact_value(ctx, "Đơn vị mặc định")
        code = ctx.get("identifier_text")
        unit_text = f"Đơn vị mặc định đang dùng là {unit}." if unit else ""
        code_text = f"Mã chuẩn dữ liệu là {code}." if code else ""
        return f"{unit_text} {code_text} Khi so sánh dữ liệu dinh dưỡng, cần kiểm tra đơn vị, khẩu phần và cách quy đổi."

    def _nutrient_labeling(self, ctx: dict[str, Any]) -> str:
        return (
            f"Thông tin ghi nhãn của {ctx['display_name']} cần được hiểu theo quy định và "
            "ngữ cảnh sản phẩm tại Việt Nam. Nếu graph chưa gắn văn bản quy định cụ thể, "
            "phần này chỉ có ý nghĩa định hướng tra cứu, không phải kết luận tuân thủ."
        )

    def _nutrient_claim(self, ctx: dict[str, Any]) -> str:
        claims = self._names(ctx, "health_claims")
        return f"Các claim sức khỏe liên quan đang có trong đồ thị gồm {claims}. Cần kiểm tra điều kiện sử dụng claim và nguồn quy định trước khi áp dụng cho nhãn hoặc nội dung truyền thông."

    def _evidence(self, ctx: dict[str, Any]) -> str:
        return (
            f"Hồ sơ của {ctx['display_name']} dựa trên {ctx.get('source_summary')}. "
            "Khi sử dụng dữ liệu, cần kiểm tra ngày rà soát, trang hoặc số bản ghi gốc nếu có, "
            "và ưu tiên nguồn chính thức cho các quyết định có tác động thực tế."
        )

    def _generic_overview(self, ctx: dict[str, Any]) -> str:
        return f"{ctx['display_name']} là một thực thể trong ViFood-KC. {ctx['summary']}"

    def _section_evidence(self, ctx: dict[str, Any], section_type: str) -> dict[str, Any]:
        evidence = dict(ctx.get("evidence") or {})
        evidence["section_type"] = section_type
        return evidence

    def _has_overview_data(self, ctx: dict[str, Any]) -> bool:
        return bool(ctx.get("display_name") and (self._has_real_summary(ctx) or ctx.get("facts") or ctx.get("identifier_text")))

    @staticmethod
    def _has_real_summary(ctx: dict[str, Any]) -> bool:
        summary = str(ctx.get("summary") or "").strip()
        return bool(summary and "được ghi nhận trong ViFood-KC." not in summary)

    @staticmethod
    def _has_evidence_data(ctx: dict[str, Any]) -> bool:
        evidence = ctx.get("evidence") or {}
        return any(
            evidence.get(key)
            for key in ("source", "source_id", "source_url", "reviewed_at", "raw_page_number", "raw_record_number")
        ) or bool(evidence.get("sources") or evidence.get("regulations"))

    def _has_related(self, ctx: dict[str, Any], relationship_key: str) -> bool:
        return bool((ctx.get("related") or {}).get(relationship_key))

    def _has_any_related(self, ctx: dict[str, Any], relationship_keys: tuple[str, ...]) -> bool:
        return any(self._has_related(ctx, key) for key in relationship_keys)

    def _has_any_context_data(self, ctx: dict[str, Any]) -> bool:
        related = ctx.get("related") or {}
        return bool(ctx.get("facts") or self._has_evidence_data(ctx) or any(related.get(key) for key in related))

    @staticmethod
    def _names(ctx: dict[str, Any], relationship_key: str, max_items: int = 8) -> str:
        items = (ctx.get("related") or {}).get(relationship_key) or []
        names = []
        for item in items[:max_items]:
            name = item.get("name_vi") or item.get("vi_name") or item.get("name") or item.get("title") or item.get("code") or item.get("id")
            if name:
                names.append(str(name))
        return ", ".join(names)

    @staticmethod
    def _fact_value(ctx: dict[str, Any], label: str) -> str:
        for fact in ctx.get("facts") or []:
            if fact.get("label") == label:
                return str(fact.get("value") or "")
        return ""
