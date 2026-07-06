import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from src.config.settings import AppSettings, GraphLabels, Neo4jSettings, load_settings
from src.db.neo4j_connection import SourceNeo4jConnection, TargetNeo4jConnection
from src.extract import AdditiveExtractor, NutrientExtractor
from src.load.neo4j_loader import Neo4jLoader
from src.state import ImportRegistry
from src.transform import SemanticContextBuilder, TemplateSectionGenerator, WikiProfileGenerator
from src.transform.source_hash import compute_source_hash
from src.validate.wiki_validator import ValidationError, WikiValidator


OUTPUT_DIR = Path("data/output")
STATE_DIR = Path("data/state")
DEFAULT_IMPORT_REGISTRY = STATE_DIR / "imported_entities.json"
ENTITY_TYPES = ("additive", "nutrient")


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
    build_parser.add_argument("--input", default=None, help="Read raw extract JSON instead of querying source Neo4j.")
    build_parser.add_argument("--limit", type=int, default=None)
    build_parser.add_argument("--output", default=None)
    build_parser.add_argument("--env-file", default=None)

    batch_parser = subparsers.add_parser(
        "batch",
        help="Extract from source, generate template wiki sections, validate, and optionally import to target.",
    )
    batch_parser.add_argument("--entity-type", "--type", dest="entity_type", required=True, choices=(*ENTITY_TYPES, "all"))
    batch_parser.add_argument("--input", default=None, help="Read raw extract JSON instead of querying source Neo4j.")
    batch_parser.add_argument("--limit", type=int, default=None)
    batch_parser.add_argument("--output", default=None)
    batch_parser.add_argument("--env-file", default=None)
    batch_parser.add_argument("--state-file", default=str(DEFAULT_IMPORT_REGISTRY))
    batch_parser.add_argument("--dry-run", action="store_true", help="Write review JSON and validate, but do not import.")
    batch_parser.add_argument("--force", action="store_true", help="Regenerate sections even when target cache matches source_hash.")
    batch_parser.add_argument("--reprocess-imported", action="store_true", help="Ignore import state file and process already imported entities again.")

    validate_parser = subparsers.add_parser("validate", help="Validate review JSON before import.")
    validate_parser.add_argument("--file", required=True)

    import_parser = subparsers.add_parser("import", help="Import review JSON into target ViFood-KG.")
    import_parser.add_argument("--file", required=True)
    import_parser.add_argument("--env-file", default=None)
    import_parser.add_argument("--state-file", default=str(DEFAULT_IMPORT_REGISTRY))

    args = parser.parse_args()
    try:
        if args.command == "extract":
            _extract(args)
        elif args.command == "build":
            _build(args)
        elif args.command == "batch":
            _batch(args)
        elif args.command == "validate":
            _validate(args)
        elif args.command == "import":
            _import(args)
    except ValidationError as exc:
        raise SystemExit(f"Validation failed:\n{exc}") from exc
    except ValueError as exc:
        raise SystemExit(f"Pipeline failed: {exc}") from exc


def _extract(args: argparse.Namespace) -> None:
    settings = load_settings(args.env_file)
    _assert_separate_neo4j(settings)
    source = SourceNeo4jConnection(settings.source_neo4j)
    try:
        raw_items = _extract_raw(source, args.type, args.limit, settings.labels)
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
    if args.input:
        raw_items = _read_raw_items(args.input, args.type, args.limit)
    else:
        source = SourceNeo4jConnection(settings.source_neo4j)
        try:
            raw_items = _extract_raw(source, args.type, args.limit, settings.labels)
        finally:
            source.close()

    items = _build_items(raw_items)

    output_type = args.type
    output = Path(args.output) if args.output else OUTPUT_DIR / f"wiki_{output_type}.json"
    _write_json(output, _payload("build", output_type, items))
    print(f"Wrote review JSON: {output}")
    print(f"Items: {len(items)}")


def _batch(args: argparse.Namespace) -> None:
    settings = load_settings(args.env_file)
    _assert_separate_neo4j(settings)

    source = None
    target = TargetNeo4jConnection(settings.target_neo4j)
    try:
        if args.input:
            raw_items = _read_raw_items(args.input, args.entity_type, None)
        else:
            source = SourceNeo4jConnection(settings.source_neo4j)
            raw_items = _extract_raw(
                source,
                args.entity_type,
                None if not args.reprocess_imported else args.limit,
                settings.labels,
            )
        extracted_count = len(raw_items)
        loader = Neo4jLoader(target)
        registry = ImportRegistry(args.state_file)
        if not args.reprocess_imported:
            raw_items, skipped_imported_count = _filter_unimported(raw_items, registry)
            if args.limit is not None:
                raw_items = raw_items[: args.limit]
        else:
            skipped_imported_count = 0
        selected_count = len(raw_items)
        items = _build_items(
            raw_items,
            loader if not args.force else None,
        )
        output_type = args.entity_type
        output = Path(args.output) if args.output else OUTPUT_DIR / f"wiki_{output_type}.json"
        payload = _payload("batch", output_type, items)
        payload["metadata"]["state_file"] = str(registry.path)
        if args.input:
            payload["metadata"]["input_file"] = str(args.input)
        payload["metadata"]["extracted_count"] = extracted_count
        payload["metadata"]["skipped_imported_count"] = skipped_imported_count
        payload["metadata"]["selected_count"] = selected_count
        _write_json(output, payload)

        if not items:
            print(f"Wrote review JSON: {output}")
            print("Items: 0")
            print("No items to import.")
            return

        errors = WikiValidator().validate_payload(payload)
        if errors:
            raise ValidationError("\n".join(errors))

        print(f"Wrote review JSON: {output}")
        print(f"Items: {len(items)}")
        if args.dry_run:
            print("Dry-run: skipped import into target ViFood-KG.")
            return

        result = loader.import_payload(payload)
        registry.mark_imported(items, output)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        print(f"Updated import state: {registry.path}")
    finally:
        if source is not None:
            source.close()
        target.close()


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
        loader = Neo4jLoader(target)
        result = loader.import_file(args.file)
        registry = ImportRegistry(args.state_file)
        registry.mark_imported(_read_items(args.file), args.file)
    finally:
        target.close()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print(f"Updated import state: {registry.path}")


def _extract_raw(
    connection: SourceNeo4jConnection,
    entity_type: str,
    limit: int | None,
    labels: GraphLabels,
) -> list[tuple[str, dict[str, Any]]]:
    extractors = {
        "additive": AdditiveExtractor(connection, labels.additive),
        "nutrient": NutrientExtractor(connection, labels.nutrient),
    }
    selected = ENTITY_TYPES if entity_type == "all" else (entity_type,)
    raw_items: list[tuple[str, dict[str, Any]]] = []
    for selected_type in selected:
        for item in extractors[selected_type].get_all(limit):
            raw_items.append((selected_type, item))
    return raw_items


def _filter_unimported(
    raw_items: list[tuple[str, dict[str, Any]]],
    registry: ImportRegistry,
) -> tuple[list[tuple[str, dict[str, Any]]], int]:
    filtered: list[tuple[str, dict[str, Any]]] = []
    skipped = 0
    for entity_type, raw_item in raw_items:
        entity_id = _raw_entity_id(raw_item)
        source_hash = compute_source_hash(raw_item, entity_type)
        if entity_id and registry.is_imported(entity_type, entity_id, source_hash):
            skipped += 1
            continue
        filtered.append((entity_type, raw_item))
    return filtered, skipped


def _raw_entity_id(raw_item: dict[str, Any]) -> str:
    entity = raw_item.get("entity") or {}
    return str(entity.get("id") or entity.get("external_code") or entity.get("code") or "")


def _build_items(
    raw_items: list[tuple[str, dict[str, Any]]],
    target_loader: Neo4jLoader | None = None,
) -> list[dict[str, Any]]:
    context_builder = SemanticContextBuilder()
    profile_generator = WikiProfileGenerator()
    section_generator = TemplateSectionGenerator()
    items: list[dict[str, Any]] = []

    for entity_type, raw_item in raw_items:
        context = context_builder.build(raw_item, entity_type)
        source_hash = compute_source_hash(raw_item, entity_type)
        profile_id = f"WIKI:{context['entity_id']}"

        cached = target_loader.get_cached_wiki(profile_id, source_hash) if target_loader else None
        if cached:
            wiki_profile = cached["wiki_profile"]
            wiki_sections = cached["wiki_sections"]
            generation_status = "cached"
        else:
            wiki_profile = profile_generator.generate(context, source_hash)
            wiki_sections = section_generator.generate(context, source_hash)
            generation_status = "template"

        if not wiki_sections:
            continue

        items.append(
            {
                "entity_id": context["entity_id"],
                "entity_type": context["entity_type"],
                "source_hash": source_hash,
                "source_entity": raw_item.get("entity") or {},
                "wiki_profile": wiki_profile,
                "wiki_sections": wiki_sections,
                "facts": context["facts"],
                "related": context["related"],
                "evidence": context["evidence"],
                "generation_status": generation_status,
            }
        )
    return items


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


def _read_items(path: str | Path) -> list[dict[str, Any]]:
    with Path(path).open("r", encoding="utf-8") as f:
        payload = json.load(f)
    items = payload.get("items") if isinstance(payload, dict) else None
    if not isinstance(items, list):
        raise ValueError(f"JSON file must contain an items list: {path}")
    return items


def _read_raw_items(
    path: str | Path,
    entity_type: str,
    limit: int | None = None,
) -> list[tuple[str, dict[str, Any]]]:
    items = _read_items(path)
    raw_items: list[tuple[str, dict[str, Any]]] = []
    for index, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"Raw item #{index} must be an object: {path}")
        item_type = str(item.get("entity_type") or "")
        if not item_type:
            raise ValueError(f"Raw item #{index} is missing entity_type: {path}")
        if entity_type != "all" and item_type != entity_type:
            continue
        if item_type not in ENTITY_TYPES:
            if entity_type == "all":
                continue
            raise ValueError(f"Raw item #{index} has unsupported entity_type {item_type!r}: {path}")
        entity = item.get("entity")
        relationships = item.get("relationships")
        if not isinstance(entity, dict) or not isinstance(relationships, dict):
            raise ValueError(
                f"Raw item #{index} must contain entity and relationships objects: {path}"
            )
        raw_items.append((item_type, {"entity": entity, "relationships": relationships}))
        if limit is not None and len(raw_items) >= limit:
            break
    return raw_items


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
