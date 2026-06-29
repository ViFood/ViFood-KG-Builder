import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from src.config.settings import AppSettings, Neo4jSettings, load_settings
from src.db.neo4j_connection import SourceNeo4jConnection, TargetNeo4jConnection
from src.extract import AdditiveExtractor, IngredientExtractor, NutrientExtractor
from src.load.neo4j_loader import Neo4jLoader
from src.transform import SemanticContextBuilder, WikiProfileGenerator, WikiSectionGenerator
from src.validate.wiki_validator import ValidationError, WikiValidator


OUTPUT_DIR = Path("data/output")
ENTITY_TYPES = ("ingredient", "additive", "nutrient")


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="python -m src.main",
        description="Batch pipeline to build ViFood-KG wiki data from ViFood-KC.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    extract_parser = subparsers.add_parser("extract", help="Extract raw data from source ViFood-KC.")
    extract_parser.add_argument("--type", required=True, choices=(*ENTITY_TYPES, "all"))
    extract_parser.add_argument("--limit", type=int, default=None)
    extract_parser.add_argument("--output", default=None)
    extract_parser.add_argument("--env-file", default=None)

    build_parser = subparsers.add_parser("build", help="Build review JSON from source ViFood-KC.")
    build_parser.add_argument("--type", required=True, choices=(*ENTITY_TYPES, "all"))
    build_parser.add_argument("--limit", type=int, default=None)
    build_parser.add_argument("--output", default=None)
    build_parser.add_argument("--env-file", default=None)

    validate_parser = subparsers.add_parser("validate", help="Validate review JSON before import.")
    validate_parser.add_argument("--file", required=True)

    import_parser = subparsers.add_parser("import", help="Import review JSON into target ViFood-KG.")
    import_parser.add_argument("--file", required=True)
    import_parser.add_argument("--env-file", default=None)

    args = parser.parse_args()
    try:
        if args.command == "extract":
            _extract(args)
        elif args.command == "build":
            _build(args)
        elif args.command == "validate":
            _validate(args)
        elif args.command == "import":
            _import(args)
    except ValidationError as exc:
        raise SystemExit(f"Validation failed:\n{exc}") from exc


def _extract(args: argparse.Namespace) -> None:
    settings = load_settings(args.env_file)
    _assert_separate_neo4j(settings)
    source = SourceNeo4jConnection(settings.source_neo4j)
    try:
        raw_items = _extract_raw(source, args.type, args.limit)
    finally:
        source.close()
    items = [
        {"entity_type": entity_type, "entity": item["entity"], "relationships": item["relationships"]}
        for entity_type, item in raw_items
    ]
    output = Path(args.output) if args.output else OUTPUT_DIR / f"raw_{args.type}.json"
    _write_json(output, _payload("extract", args.type, items))
    print(f"Wrote raw extract JSON: {output}")


def _build(args: argparse.Namespace) -> None:
    settings = load_settings(args.env_file)
    _assert_separate_neo4j(settings)
    source = SourceNeo4jConnection(settings.source_neo4j)
    try:
        raw_items = _extract_raw(source, args.type, args.limit)
    finally:
        source.close()

    items = []
    for entity_type, raw_item in raw_items:
        context = SemanticContextBuilder().build(raw_item, entity_type)
        wiki_sections = WikiSectionGenerator().generate(context)
        if not wiki_sections:
            continue
        item = {
            "entity_id": context["entity_id"],
            "entity_type": context["entity_type"],
            "source_entity": raw_item.get("entity") or {},
            "wiki_profile": WikiProfileGenerator().generate(context),
            "wiki_sections": wiki_sections,
            "facts": context["facts"],
            "related": context["related"],
            "evidence": context["evidence"],
        }
        items.append(item)

    output_type = args.type
    output = Path(args.output) if args.output else OUTPUT_DIR / f"wiki_{output_type}.json"
    _write_json(output, _payload("build", output_type, items))
    print(f"Wrote review JSON: {output}")
    print(f"Items: {len(items)}")


def _validate(args: argparse.Namespace) -> None:
    errors = WikiValidator().validate_file(args.file)
    if errors:
        raise ValidationError("\n".join(errors))
    print(f"Valid wiki JSON: {args.file}")


def _import(args: argparse.Namespace) -> None:
    settings = load_settings(args.env_file)
    _assert_separate_neo4j(settings)
    target = TargetNeo4jConnection(settings.target_neo4j)
    try:
        result = Neo4jLoader(target).import_file(args.file)
    finally:
        target.close()
    print(json.dumps(result, ensure_ascii=False, indent=2))


def _extract_raw(
    connection: SourceNeo4jConnection,
    entity_type: str,
    limit: int | None,
) -> list[tuple[str, dict[str, Any]]]:
    extractors = {
        "ingredient": IngredientExtractor(connection),
        "additive": AdditiveExtractor(connection),
        "nutrient": NutrientExtractor(connection),
    }
    selected = ENTITY_TYPES if entity_type == "all" else (entity_type,)
    raw_items: list[tuple[str, dict[str, Any]]] = []
    for selected_type in selected:
        for item in extractors[selected_type].get_all(limit):
            raw_items.append((selected_type, item))
    return raw_items


def _assert_separate_neo4j(settings: AppSettings) -> None:
    if _same_neo4j(settings.source_neo4j, settings.target_neo4j):
        raise SystemExit(
            "SOURCE_NEO4J_* and TARGET_NEO4J_* point to the same Neo4j database. "
            "ViFood-KC source and ViFood-KG target must be configured separately."
        )


def _same_neo4j(left: Neo4jSettings, right: Neo4jSettings) -> bool:
    return (
        left.uri == right.uri
        and left.user == right.user
        and left.database == right.database
    )


def _payload(stage: str, entity_type: str, items: Any) -> dict[str, Any]:
    return {
        "metadata": {
            "project": "ViFood-KG-Builder",
            "stage": stage,
            "source_graph": "ViFood-KC",
            "target_graph": "ViFood-KG",
            "entity_type": entity_type,
            "generated_at": datetime.now(UTC).isoformat(),
            "review_required_before_import": stage == "build",
        },
        "items": items,
    }


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(_json_safe(payload), f, ensure_ascii=False, indent=2)
        f.write("\n")


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if hasattr(value, "iso_format"):
        return value.iso_format()
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


if __name__ == "__main__":
    main()
