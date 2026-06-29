from src.transform.semantic_context_builder import SemanticContextBuilder
from src.transform.wiki_profile_generator import WikiProfileGenerator
from src.transform.source_hash import compute_source_hash
from src.validate.wiki_validator import WikiValidator


def test_additive_builds_valid_wiki_item() -> None:
    raw = {
        "entity": {
            "id": "additive:e330",
            "name_vi": "Acid citric",
            "name": "Citric acid",
            "ins": "330",
            "description": "Acid citric là phụ gia dùng để điều chỉnh độ chua.",
        },
        "relationships": {
            "functions": [{"id": "function:acid", "name": "Chất điều chỉnh độ acid"}],
            "sources": [{"id": "source:test", "title": "Test source"}],
            "regulations": [],
        },
    }
    context = SemanticContextBuilder().build(raw, "additive")
    source_hash = compute_source_hash(raw, "additive")
    item = {
        "entity_id": context["entity_id"],
        "entity_type": context["entity_type"],
        "source_hash": source_hash,
        "source_entity": raw["entity"],
        "wiki_profile": WikiProfileGenerator().generate(context, source_hash),
        "wiki_sections": [
            {
                "id": "WIKI:additive:e330:overview",
                "title": "Tổng quan",
                "content": "Acid citric là một phụ gia được mô tả trong dữ liệu nguồn với vai trò điều chỉnh độ chua trong thực phẩm.",
                "section_type": "overview",
                "order": 1,
                "status": "draft",
                "source_hash": source_hash,
                "generated_by": "ai",
            }
        ],
        "facts": context["facts"],
        "related": context["related"],
        "evidence": context["evidence"],
    }
    errors = WikiValidator().validate_payload({"items": [item]})
    assert errors == []


def test_semantic_context_excludes_internal_metadata_from_facts() -> None:
    raw = {
        "entity": {
            "id": "ADDITIVE:INS_100_I",
            "name_vi": "Curcumin",
            "ins": "100(i)",
            "status": "active",
            "reviewed_at": "2026-06-23",
            "created_at": "2026-06-22T13:06:02Z",
            "updated_at": "2026-06-23T07:26:45Z",
        },
        "relationships": {},
    }

    context = SemanticContextBuilder().build(raw, "additive")

    assert context["facts"] == [{"label": "Mã INS", "value": "100(i)"}]
    assert "ViFood-KC" not in context["summary"]
