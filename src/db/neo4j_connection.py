from typing import Any

from neo4j import GraphDatabase

from src.config.settings import Neo4jSettings


class Neo4jConnection:
    role = "neo4j"

    def __init__(self, settings: Neo4jSettings) -> None:
        if not settings.password:
            raise ValueError(
                f"{self.role} Neo4j password is empty. Configure the matching "
                "SOURCE_NEO4J_PASSWORD or TARGET_NEO4J_PASSWORD in .env."
            )
        self.settings = settings
        self.database = settings.database
        self.driver = GraphDatabase.driver(settings.uri, auth=(settings.user, settings.password))

    def close(self) -> None:
        self.driver.close()

    def read(self, query: str, parameters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        with self.driver.session(database=self.database) as session:
            return session.execute_read(self._run, query, parameters or {})

    def write(self, query: str, parameters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        with self.driver.session(database=self.database) as session:
            return session.execute_write(self._run, query, parameters or {})

    @staticmethod
    def _run(tx: Any, query: str, parameters: dict[str, Any]) -> list[dict[str, Any]]:
        return [record.data() for record in tx.run(query, **parameters)]


class SourceNeo4jConnection(Neo4jConnection):
    role = "source ViFood-KC"


class TargetNeo4jConnection(Neo4jConnection):
    role = "target ViFood-KG"
