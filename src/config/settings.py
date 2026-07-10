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
    additive: str = "Additive"
    nutrient: str = "Nutrient"
    source: str = "Source"
    regulation: str = "Regulation"


@dataclass(frozen=True)
class AppSettings:
    source_neo4j: Neo4jSettings
    target_neo4j: Neo4jSettings
    labels: GraphLabels
    openai_api_key: str | None
    model: str | None
    aws_region: str | None
    aws_s3_bucket: str | None
    kie_model_url: str


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
            additive=os.getenv("ADDITIVE_LABEL", "Additive"),
            nutrient=os.getenv("NUTRIENT_LABEL", "Nutrient"),
            source=os.getenv("SOURCE_LABEL", "Source"),
            regulation=os.getenv("REGULATION_LABEL", "Regulation"),
        ),
        openai_api_key=os.getenv("OPENAI_API_KEY"),
        model=os.getenv("MODEL"),
        aws_region=(
            os.getenv("AWS_REGION")
            or os.getenv("AWS_DEFAULT_REGION")
        ),
        aws_s3_bucket=os.getenv("AWS_S3_BUCKET"),
        kie_model_url=os.getenv("KIE_MODEL_URL", "http://localhost:8001"),
    )
