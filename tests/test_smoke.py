from src.transform.semantic_context_builder import SemanticContextBuilder
from src.transform.wiki_profile_generator import WikiProfileGenerator
from src.transform.wiki_section_generator import WikiSectionGenerator
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
    item = {
        "entity_id": context["entity_id"],
        "entity_type": context["entity_type"],
        "wiki_profile": WikiProfileGenerator().generate(context),
        "wiki_sections": WikiSectionGenerator().generate(context),
        "facts": context["facts"],
        "related": context["related"],
        "evidence": context["evidence"],
    }
    errors = WikiValidator().validate_payload({"items": [item]})
    assert errors == []
