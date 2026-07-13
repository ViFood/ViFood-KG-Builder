import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass(frozen=True)
class Neo4jSettings:
    uri: str
    user: str
    password: str
    database: str


@dataclass(frozen=True)
class GraphLabels:
    ingredient: str = "Ingredient"
    additive: str = "Additive"
    nutrient: str = "Nutrient"
    source: str = "Source"
    regulation: str = "Regulation"


@dataclass(frozen=True)
class KGContractSettings:
    path: str | None
    version: str | None


@dataclass(frozen=True)
class WikidataSettings:
    sparql_url: str
    entity_base_url: str
    source_id: str
    source_name: str
    source_url: str
    user_agent: str
    search_language: str
    search_limit: int
    request_timeout_seconds: int
    detail_timeout_seconds: int
    food_signal_qids: tuple[str, ...]


@dataclass(frozen=True)
class AppSettings:
    source_neo4j: Neo4jSettings
    target_neo4j: Neo4jSettings
    labels: GraphLabels
    kg_contract: KGContractSettings
    wikidata: WikidataSettings
    openai_api_key: str | None
    model: str | None
    aws_region: str | None
    aws_s3_bucket: str | None
    kie_model_url: str
    kie_model_timeout_seconds: int


def load_settings(env_file: str | None = None) -> AppSettings:
    load_dotenv(env_file)
    return AppSettings(
        source_neo4j=Neo4jSettings(
            uri=os.getenv("SOURCE_NEO4J_URI", "bolt://localhost:7687"),
            user=os.getenv("SOURCE_NEO4J_USER", "neo4j"),
            password=os.getenv("SOURCE_NEO4J_PASSWORD", ""),
            database=os.getenv("SOURCE_NEO4J_DATABASE", "neo4j"),
        ),
        target_neo4j=Neo4jSettings(
            uri=os.getenv("TARGET_NEO4J_URI", "bolt://localhost:7688"),
            user=os.getenv("TARGET_NEO4J_USER", "neo4j"),
            password=os.getenv("TARGET_NEO4J_PASSWORD", ""),
            database=os.getenv("TARGET_NEO4J_DATABASE", "neo4j"),
        ),
        labels=GraphLabels(
            ingredient=os.getenv("INGREDIENT_LABEL", "Ingredient"),
            additive=os.getenv("ADDITIVE_LABEL", "Additive"),
            nutrient=os.getenv("NUTRIENT_LABEL", "Nutrient"),
            source=os.getenv("SOURCE_LABEL", "Source"),
            regulation=os.getenv("REGULATION_LABEL", "Regulation"),
        ),
        kg_contract=KGContractSettings(
            path=os.getenv("KG_CONTRACT_PATH"),
            version=os.getenv("KG_CONTRACT_VERSION"),
        ),
        wikidata=WikidataSettings(
            sparql_url=os.getenv(
                "WIKIDATA_SPARQL_URL",
                "https://query.wikidata.org/sparql",
            ),
            entity_base_url=os.getenv(
                "WIKIDATA_ENTITY_BASE_URL",
                "https://www.wikidata.org/wiki",
            ).rstrip("/"),
            source_id=os.getenv("WIKIDATA_SOURCE_ID", "SOURCE:WIKIDATA"),
            source_name=os.getenv("WIKIDATA_SOURCE_NAME", "Wikidata"),
            source_url=os.getenv("WIKIDATA_SOURCE_URL", "https://www.wikidata.org/"),
            user_agent=os.getenv(
                "WIKIDATA_USER_AGENT",
                "ViFood-KG-Builder/1.0",
            ),
            search_language=os.getenv("WIKIDATA_SEARCH_LANGUAGE", "vi"),
            search_limit=_env_int("WIKIDATA_SEARCH_LIMIT", 10),
            request_timeout_seconds=_env_int("WIKIDATA_REQUEST_TIMEOUT_SECONDS", 30),
            detail_timeout_seconds=_env_int("WIKIDATA_DETAIL_TIMEOUT_SECONDS", 45),
            food_signal_qids=_env_tuple(
                "WIKIDATA_FOOD_SIGNAL_QIDS",
                (
                    "Q2095",
                    "Q25403900",
                    "Q189567",
                    "Q19861951",
                    "Q193598",
                    "Q40050",
                    "Q11004",
                    "Q59199015",
                ),
            ),
        ),
        openai_api_key=os.getenv("OPENAI_API_KEY"),
        model=os.getenv("MODEL"),
        aws_region=(
            os.getenv("AWS_REGION")
            or os.getenv("AWS_DEFAULT_REGION")
        ),
        aws_s3_bucket=os.getenv("AWS_S3_BUCKET"),
        kie_model_url=os.getenv("KIE_MODEL_URL", "http://localhost:8001"),
        kie_model_timeout_seconds=_env_int("KIE_MODEL_TIMEOUT_SECONDS", 90),
    )


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value in (None, ""):
        return default

    try:
        return int(value)
    except ValueError:
        return default


def _env_tuple(name: str, default: tuple[str, ...]) -> tuple[str, ...]:
    value = os.getenv(name)
    if not value:
        return default

    items = tuple(
        item.strip()
        for item in value.split(",")
        if item.strip()
    )
    return items or default
