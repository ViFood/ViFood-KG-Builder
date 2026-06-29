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
class AppSettings:
    source_neo4j: Neo4jSettings
    target_neo4j: Neo4jSettings
    labels: GraphLabels


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
    )
