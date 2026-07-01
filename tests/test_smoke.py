from src.main import _filter_unimported
from src.state import ImportRegistry
from src.transform.semantic_context_builder import SemanticContextBuilder
from src.transform.ai_section_generator import AISectionGenerator
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
                "content": "Acid citric là một phụ gia thực phẩm có mã INS 330.",
                "section_type": "overview",
                "order": 1,
                "status": "draft",
                "source_hash": source_hash,
                "generated_by": "gemini",
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


def test_ai_prompt_keeps_section_purposes_separate() -> None:
    prompt = AISectionGenerator._prompt_text({"entity": {"display_name": "Curcumin"}})

    assert "overview: chỉ giải thích entity là gì" in prompt
    assert "Không nêu phân loại, vai trò" in prompt
    assert "classification_and_role: chỉ nêu entity thuộc nhóm nào" in prompt
    assert "common_foods: chỉ nêu chất này thường gặp" in prompt
    assert "health_note: chỉ nêu điều cần lưu ý cho sức khỏe" in prompt
    assert "source_and_regulation: nêu chung nguồn tham khảo" in prompt
    assert "không gom nhiều loại thông tin" in prompt


def test_import_registry_filters_previously_imported_entities(tmp_path) -> None:
    raw_imported = {
        "entity": {"id": "ADDITIVE:INS_100_I", "name": "Curcumin", "ins": "100(i)"},
        "relationships": {"functions": [{"name": "Phẩm màu"}]},
    }
    raw_new = {
        "entity": {"id": "ADDITIVE:INS_100_II", "name": "Turmeric", "ins": "100(ii)"},
        "relationships": {"functions": [{"name": "Phẩm màu"}]},
    }
    imported_hash = compute_source_hash(raw_imported, "additive")
    registry = ImportRegistry(tmp_path / "imported_entities.json")
    registry.mark_imported(
        [
            {
                "entity_id": "ADDITIVE:INS_100_I",
                "entity_type": "additive",
                "source_hash": imported_hash,
                "wiki_profile": {"id": "WIKI:ADDITIVE:INS_100_I"},
                "wiki_sections": [{"section_type": "overview"}],
            }
        ]
    )

    filtered, skipped = _filter_unimported(
        [("additive", raw_imported), ("additive", raw_new)],
        registry,
    )

    assert skipped == 1
    assert [item[1]["entity"]["id"] for item in filtered] == ["ADDITIVE:INS_100_II"]


def test_source_hash_is_stable_for_relationship_order() -> None:
    left = {
        "entity": {"id": "ADDITIVE:INS_100_I", "ins": "100(i)"},
        "relationships": {
            "functions": [{"id": "f2", "name": "B"}, {"id": "f1", "name": "A"}],
            "sources": [{"id": "s1"}],
        },
    }
    right = {
        "entity": {"ins": "100(i)", "id": "ADDITIVE:INS_100_I"},
        "relationships": {
            "sources": [{"id": "s1"}],
            "functions": [{"id": "f1", "name": "A"}, {"id": "f2", "name": "B"}],
        },
    }

    assert compute_source_hash(left, "additive") == compute_source_hash(right, "additive")
