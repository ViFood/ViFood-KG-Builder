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
class AISettings:
    api_key: str
    model: str
    max_retries: int
    retry_base_seconds: float
    request_delay_seconds: float


@dataclass(frozen=True)
class AppSettings:
    source_neo4j: Neo4jSettings
    target_neo4j: Neo4jSettings
    labels: GraphLabels
    ai: AISettings


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
        ai=AISettings(
            api_key=os.getenv("GEMINI_API_KEY", ""),
            model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
            max_retries=_int_env("GEMINI_MAX_RETRIES", 6),
            retry_base_seconds=_float_env("GEMINI_RETRY_BASE_SECONDS", 5.0),
            request_delay_seconds=_float_env("GEMINI_REQUEST_DELAY_SECONDS", 1.0),
        ),
    )


def _int_env(name: str, default: int) -> int:
    value = os.getenv(name)
    if value in (None, ""):
        return default
    return int(value)


def _float_env(name: str, default: float) -> float:
    value = os.getenv(name)
    if value in (None, ""):
        return default
    return float(value)
