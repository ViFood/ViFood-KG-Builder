import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from src.config.settings import AppSettings, GraphLabels, Neo4jSettings, load_settings
from src.db.neo4j_connection import SourceNeo4jConnection, TargetNeo4jConnection
from src.extract import AdditiveExtractor, NutrientExtractor
from src.load.neo4j_loader import Neo4jLoader


OUTPUT_DIR = Path("data/output")
ENTITY_TYPES = ("additive", "nutrient")


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="python -m src.main",
        description="Replicate ViFood-KC additive/nutrient graph data into target Neo4j.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    extract_parser = subparsers.add_parser("extract", help="Extract raw graph data from source ViFood-KC.")
    extract_parser.add_argument("--type", required=True, choices=(*ENTITY_TYPES, "all"))
    extract_parser.add_argument("--limit", type=int, default=None)
    extract_parser.add_argument("--output", default=None)
    extract_parser.add_argument("--env-file", default=None)

    build_parser = subparsers.add_parser("build", help="Build import JSON without querying source Neo4j again.")
    build_parser.add_argument("--type", required=True, choices=(*ENTITY_TYPES, "all"))
    build_parser.add_argument("--input", default=None, help="Read raw extract JSON instead of querying source Neo4j.")
    build_parser.add_argument("--limit", type=int, default=None)
    build_parser.add_argument("--output", default=None)
    build_parser.add_argument("--env-file", default=None)

    batch_parser = subparsers.add_parser(
        "batch",
        help="Extract or read raw data, validate, and optionally import to target Neo4j.",
    )
    batch_parser.add_argument("--entity-type", "--type", dest="entity_type", required=True, choices=(*ENTITY_TYPES, "all"))
    batch_parser.add_argument("--input", default=None, help="Read raw extract JSON instead of querying source Neo4j.")
    batch_parser.add_argument("--limit", type=int, default=None)
    batch_parser.add_argument("--output", default=None)
    batch_parser.add_argument("--env-file", default=None)
    batch_parser.add_argument("--dry-run", action="store_true", help="Write import JSON and validate, but do not import.")

    validate_parser = subparsers.add_parser("validate", help="Validate raw/import JSON before import.")
    validate_parser.add_argument("--file", required=True)

    import_parser = subparsers.add_parser("import", help="Import raw/import JSON into target Neo4j.")
    import_parser.add_argument("--file", required=True)
    import_parser.add_argument("--env-file", default=None)

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
    items = _items_from_raw(raw_items)
    output = Path(args.output) if args.output else OUTPUT_DIR / f"raw_{args.type}.json"
    _write_json(output, _payload("extract", args.type, items))
    print(f"Wrote raw extract JSON: {output}")
    print(f"Items: {len(items)}")


def _build(args: argparse.Namespace) -> None:
    settings = load_settings(args.env_file)
    _assert_separate_neo4j(settings)
    raw_items = _load_raw_items(args.input, args.type, args.limit, settings)
    items = _items_from_raw(raw_items)
    output = Path(args.output) if args.output else OUTPUT_DIR / f"graph_{args.type}.json"
    payload = _payload("build", args.type, items)
    Neo4jLoader.validate_payload(payload)
    _write_json(output, payload)
    print(f"Wrote import JSON: {output}")
    print(f"Items: {len(items)}")


def _batch(args: argparse.Namespace) -> None:
    settings = load_settings(args.env_file)
    _assert_separate_neo4j(settings)
    raw_items = _load_raw_items(args.input, args.entity_type, args.limit, settings)
    items = _items_from_raw(raw_items)
    output = Path(args.output) if args.output else OUTPUT_DIR / f"graph_{args.entity_type}.json"
    payload = _payload("batch", args.entity_type, items)
    if args.input:
        payload["metadata"]["input_file"] = str(args.input)
    Neo4jLoader.validate_payload(payload)
    _write_json(output, payload)
    print(f"Wrote import JSON: {output}")
    print(f"Items: {len(items)}")
    if args.dry_run:
        print("Dry-run: skipped import into target Neo4j.")
        return

    target = TargetNeo4jConnection(settings.target_neo4j)
    try:
        result = Neo4jLoader(target).import_payload(payload)
    finally:
        target.close()
    print(json.dumps(result, ensure_ascii=False, indent=2))


def _validate(args: argparse.Namespace) -> None:
    with Path(args.file).open("r", encoding="utf-8") as f:
        payload = json.load(f)
    Neo4jLoader.validate_payload(payload)
    print(f"Valid import JSON: {args.file}")


def _import(args: argparse.Namespace) -> None:
    settings = load_settings(args.env_file)
    _assert_separate_neo4j(settings)
    target = TargetNeo4jConnection(settings.target_neo4j)
    try:
        result = Neo4jLoader(target).import_file(args.file)
    finally:
        target.close()
    print(json.dumps(result, ensure_ascii=False, indent=2))


def _load_raw_items(
    input_path: str | None,
    entity_type: str,
    limit: int | None,
    settings: AppSettings,
) -> list[tuple[str, dict[str, Any]]]:
    if input_path:
        return _read_raw_items(input_path, entity_type, limit)

    source = SourceNeo4jConnection(settings.source_neo4j)
    try:
        return _extract_raw(source, entity_type, limit, settings.labels)
    finally:
        source.close()


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


def _items_from_raw(raw_items: list[tuple[str, dict[str, Any]]]) -> list[dict[str, Any]]:
    return [
        {"entity_type": entity_type, "entity": item["entity"], "relationships": item["relationships"]}
        for entity_type, item in raw_items
    ]


def _assert_separate_neo4j(settings: AppSettings) -> None:
    if _same_neo4j(settings.source_neo4j, settings.target_neo4j):
        raise SystemExit(
            "SOURCE_NEO4J_* and TARGET_NEO4J_* point to the same Neo4j database. "
            "Source and target must be configured separately."
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
            "content_model": "source_graph",
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
