import json
from typing import Any

from src.config.settings import AISettings


SECTION_TITLES = {
    "overview": "Tổng quan",
    "role_and_usage": "Vai trò và cách dùng",
    "common_foods": "Thường gặp trong thực phẩm",
    "regulation": "Quy định và nguồn tham khảo",
    "consumer_note": "Lưu ý cho người dùng",
}

SECTION_ORDER = tuple(SECTION_TITLES)

FORBIDDEN_TERMS = (
    "graph",
    "node",
    "relationship",
    "hồ sơ",
    "dữ liệu hiện liên kết",
    "được ghi nhận trong ViFood-KC",
    "ViFood-KC",
)


class AISectionGenerator:
    def __init__(self, settings: AISettings) -> None:
        if not settings.api_key:
            raise ValueError("GEMINI_API_KEY is required to generate WikiSection content with Gemini.")
        self.settings = settings

    def generate(self, context: dict[str, Any], source_hash: str) -> list[dict[str, Any]]:
        payload = self._prompt_payload(context)
        response = self._call_model(payload)
        sections = self._normalize_sections(response, context, source_hash)
        return sections

    def _call_model(self, payload: dict[str, Any]) -> dict[str, Any]:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=self.settings.api_key)
        response = client.models.generate_content(
            model=self.settings.model,
            contents=self._prompt_text(payload),
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.2,
            ),
        )
        content = response.text or "{}"
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Gemini returned invalid JSON: {content}") from exc
        if not isinstance(parsed, dict):
            raise ValueError("Gemini response must be a JSON object.")
        return parsed

    @staticmethod
    def _prompt_text(payload: dict[str, Any]) -> str:
        return (
            "Bạn là biên tập viên kiến thức thực phẩm cho người dùng app.\n"
            "Chỉ sử dụng dữ liệu JSON được cung cấp bên dưới. Không thêm kiến thức ngoài.\n"
            "Viết tiếng Việt tự nhiên, dễ hiểu, có tính giáo dục và trung lập.\n"
            "Không dùng các từ/cụm: graph, node, relationship, hồ sơ, dữ liệu hiện liên kết, "
            "được ghi nhận trong ViFood-KC, ViFood-KC.\n"
            "Chỉ viết thông tin có thể suy ra trực tiếp từ field trong JSON.\n"
            "Không tự suy đoán món ăn thường gặp, công dụng, mức độ an toàn, rủi ro hoặc quy định nếu JSON không có dữ liệu tương ứng.\n"
            "Không kết luận an toàn tuyệt đối hoặc nguy hiểm tuyệt đối.\n"
            "Tách nội dung theo đúng mục đích từng section, không gom nhiều loại thông tin vào cùng một section và không lặp lại cùng một ý ở nhiều section.\n"
            "Quy tắc tách section:\n"
            "- overview: chỉ giới thiệu ngắn entity là gì, tên, mã định danh chính. Không nêu chức năng, nhóm thực phẩm, quy định, nguồn hay lưu ý tiêu dùng.\n"
            "- role_and_usage: chỉ nêu chức năng/vai trò/cách dùng khi JSON có related.functions hoặc field tương đương. Không nêu danh sách thực phẩm hay quy định.\n"
            "- common_foods: chỉ nêu nhóm thực phẩm hoặc bối cảnh thực phẩm khi JSON có related.permitted_in hoặc field tương đương. Không nêu chức năng hay quy định.\n"
            "- regulation: chỉ nêu văn bản, nguồn, quy định, ngày/số hiệu/trang nguồn khi JSON có sources, regulations hoặc evidence. Không nêu chức năng hay nhóm thực phẩm.\n"
            "- consumer_note: chỉ nêu cách người dùng nên hiểu/đọc thông tin trên nhãn dựa trên dữ liệu đã có. Không thêm cảnh báo sức khỏe nếu JSON không có dữ liệu.\n"
            "Nếu một section không có dữ liệu riêng đúng mục đích thì bỏ section đó.\n"
            "Output chỉ là JSON object có key `sections`.\n"
            "Mỗi section gồm `section_type` và `content`.\n"
            "section_type chỉ được là: overview, role_and_usage, common_foods, regulation, consumer_note.\n"
            "Không markdown, không bullet nếu không cần.\n\n"
            "Dữ liệu nguồn:\n"
            f"{json.dumps(payload, ensure_ascii=False, indent=2)}"
        )

    def _normalize_sections(
        self,
        response: dict[str, Any],
        context: dict[str, Any],
        source_hash: str,
    ) -> list[dict[str, Any]]:
        raw_sections = response.get("sections") or []
        if not isinstance(raw_sections, list):
            raise ValueError("AI response `sections` must be a list.")

        sections_by_type: dict[str, str] = {}
        for raw in raw_sections:
            if not isinstance(raw, dict):
                continue
            section_type = str(raw.get("section_type") or "").strip()
            content = str(raw.get("content") or "").strip()
            if section_type not in SECTION_TITLES or not content:
                continue
            if self._has_forbidden_terms(content):
                raise ValueError(
                    f"AI section {context['entity_id']}:{section_type} contains forbidden system wording."
                )
            sections_by_type.setdefault(section_type, content)

        sections: list[dict[str, Any]] = []
        for section_type in SECTION_ORDER:
            content = sections_by_type.get(section_type)
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
                    "generated_by": "gemini",
                }
            )
        return sections

    @staticmethod
    def _has_forbidden_terms(content: str) -> bool:
        lowered = content.lower()
        return any(term.lower() in lowered for term in FORBIDDEN_TERMS)

    @staticmethod
    def _prompt_payload(context: dict[str, Any]) -> dict[str, Any]:
        related = context.get("related") or {}
        evidence = context.get("evidence") or {}
        return {
            "entity": {
                "id": context.get("entity_id"),
                "type": context.get("entity_type"),
                "display_name": context.get("display_name"),
                "secondary_name": context.get("secondary_name"),
                "identifier": context.get("identifier_text"),
                "summary": context.get("summary"),
                "facts": context.get("facts") or [],
            },
            "related": {
                key: _compact_nodes(value)
                for key, value in related.items()
                if isinstance(value, list) and value
            },
            "evidence": {
                key: value
                for key, value in evidence.items()
                if key not in ("sources", "regulations") and value not in (None, "", [])
            },
            "sources": _compact_nodes(evidence.get("sources") or []),
            "regulations": _compact_nodes(evidence.get("regulations") or []),
        }


def _compact_nodes(nodes: list[dict[str, Any]], limit: int = 12) -> list[dict[str, Any]]:
    compacted = []
    keep_keys = (
        "id",
        "name_vi",
        "vi_name",
        "name",
        "title",
        "code",
        "ins",
        "description",
        "function",
        "max_level",
        "unit",
        "url",
    )
    for node in nodes[:limit]:
        compacted.append({key: node.get(key) for key in keep_keys if node.get(key) not in (None, "", [])})
    return compacted
