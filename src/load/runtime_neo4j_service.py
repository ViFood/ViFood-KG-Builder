from neo4j import GraphDatabase
import re
import unicodedata

from src.config.settings import load_settings


class Neo4jService:
    def __init__(self):
        self.settings = load_settings()
        self.neo4j = self.settings.target_neo4j

    @property
    def is_configured(self) -> bool:
        return bool(
            self.neo4j.uri
            and self.neo4j.user
            and self.neo4j.password
        )

    def get_nutrient_catalog(self) -> list[dict]:
        if not self.is_configured:
            return []

        return self._execute_read(
            self._get_nutrient_catalog_tx
        )

    def sync_nutrient(
        self,
        nutrient: dict
    ) -> dict:
        tagname = (
            nutrient.get("tagname") or ""
        ).strip().upper()

        if not self.is_configured:
            return {
                "id": None,
                "name": nutrient["name"],
                "value": nutrient.get("value"),
                "unit": nutrient.get("unit")
            }

        if not tagname:
            return {
                "id": None,
                "name": nutrient["name"],
                "value": nutrient.get("value"),
                "unit": nutrient.get("unit")
            }

        normalized_name = self._normalize_name(
            nutrient["name"]
        )
        nutrient_id = self._build_nutrient_id(
            normalized_name
        )

        return self._execute_write(
            self._sync_nutrient_tx,
            nutrient,
            normalized_name,
            nutrient_id
        )

    def match_existing_nutrient(
        self,
        nutrient: dict
    ) -> dict | None:
        if not self.is_configured:
            return None

        normalized_name = self._normalize_name(
            nutrient["name"]
        )

        return self._execute_read(
            self._match_existing_nutrient_tx,
            nutrient,
            normalized_name
        )

    def sync_additive(
        self,
        additive: dict
    ) -> dict:
        ins = (
            additive.get("ins") or ""
        ).strip().upper()

        if not self.is_configured:
            return {
                "id": None,
                "name": additive.get("name"),
                "ins": ins or None
            }

        if not ins:
            return {
                "id": None,
                "name": additive.get("name"),
                "ins": None
            }

        return self._execute_write(
            self._sync_additive_tx,
            additive,
            ins
        )

    def _execute_read(self, tx_func, *args):
        driver = GraphDatabase.driver(
            self.neo4j.uri,
            auth=(
                self.neo4j.user,
                self.neo4j.password
            )
        )

        try:
            session_kwargs = {}

            if self.neo4j.database:
                session_kwargs["database"] = self.neo4j.database

            with driver.session(**session_kwargs) as session:
                return session.execute_read(
                    tx_func,
                    *args
                )
        finally:
            driver.close()

    def _execute_write(self, tx_func, *args):
        driver = GraphDatabase.driver(
            self.neo4j.uri,
            auth=(
                self.neo4j.user,
                self.neo4j.password
            )
        )

        try:
            session_kwargs = {}

            if self.neo4j.database:
                session_kwargs["database"] = self.neo4j.database

            with driver.session(**session_kwargs) as session:
                return session.execute_write(
                    tx_func,
                    *args
                )
        finally:
            driver.close()

    def _normalize_name(self, value: str) -> str:
        normalized = value.strip().lower()
        normalized = unicodedata.normalize("NFD", normalized)
        normalized = "".join(
            char
            for char in normalized
            if unicodedata.category(char) != "Mn"
        )
        normalized = normalized.replace("đ", "d")
        normalized = re.sub(r"[^a-z0-9]+", "_", normalized)
        normalized = normalized.strip("_")

        return normalized

    def _build_nutrient_id(self, normalized_name: str) -> str:
        return f"NUTRIENT:{normalized_name.upper()}"

    @staticmethod
    def _get_nutrient_catalog_tx(tx) -> list[dict]:
        result = tx.run(
            """
            MATCH (n:Nutrient)
            OPTIONAL MATCH (a:Alias)-[:REFERS_TO]->(n)
            RETURN
                n.id AS id,
                elementId(n) AS element_id,
                coalesce(n.name, n.id) AS name,
                n.normalized_name AS normalized_name,
                collect({
                    id: a.id,
                    name: a.name,
                    normalized_name: a.normalized_name
                }) AS aliases
            ORDER BY id
            """
        )

        return [
            {
                **record.data(),
                "aliases": [
                    alias
                    for alias in record["aliases"]
                    if alias["id"] or alias["name"] or alias["normalized_name"]
                ]
            }
            for record in result
        ]

    @staticmethod
    def _match_existing_nutrient_tx(
        tx,
        nutrient: dict,
        normalized_name: str
    ) -> dict | None:
        nutrients = tx.run(
            """
            MATCH (n:Nutrient)
            RETURN
                n.id AS id,
                elementId(n) AS element_id,
                n.name AS name,
                n.name_vi AS name_vi
            """
        )

        for record in nutrients:
            candidate_names = [
                record["name"],
                record["name_vi"]
            ]
            candidate_names = [
                name
                for name in candidate_names
                if name
            ]

            if any(
                Neo4jService._normalize_text(name) == normalized_name
                for name in candidate_names
            ):
                return {
                    "id": record["id"] or record["element_id"],
                    "name": nutrient["name"],
                    "value": nutrient.get("value"),
                    "unit": nutrient.get("unit")
                }

        alias_match = tx.run(
            """
            MATCH (a:Alias)-[:REFERS_TO]->(n:Nutrient)
            WHERE a.normalized_name = $normalized_name
               OR toLower(coalesce(a.name, "")) = $lower_name
            RETURN
                n.id AS id,
                elementId(n) AS element_id
            LIMIT 1
            """,
            normalized_name=normalized_name,
            lower_name=nutrient["name"].strip().lower()
        ).single()

        if not alias_match:
            return None

        return {
            "id": alias_match["id"] or alias_match["element_id"],
            "name": nutrient["name"],
            "value": nutrient.get("value"),
            "unit": nutrient.get("unit")
        }

    @staticmethod
    def _sync_nutrient_tx(
        tx,
        nutrient: dict,
        normalized_name: str,
        nutrient_id: str
    ) -> dict:
        tagname = (
            nutrient.get("tagname") or ""
        ).strip().upper()

        existing = tx.run(
            """
            OPTIONAL MATCH (direct:Nutrient)
            WHERE ($tagname <> "" AND (
                    direct.external_code = $tagname
                    OR direct.tagname = $tagname
                    OR direct.id = "NUTRIENT:INFOODS_" + $tagname
                    OR direct.id = "NUTRIENT:" + $tagname
                ))
            WITH collect(direct)[0] AS n
            RETURN
                n.id AS id,
                elementId(n) AS element_id,
                n.name AS name,
                n.name_vi AS name_vi
            LIMIT 1
            """,
            tagname=tagname
        ).single()

        if not existing or not existing["element_id"]:
            required_metadata = {
                "infoods_name": nutrient.get("infoods_name"),
                "name_vi": nutrient.get("name_vi"),
                "default_unit": nutrient.get("default_unit")
            }
            missing_metadata = [
                key
                for key, value in required_metadata.items()
                if not value
            ]

            if missing_metadata:
                raise ValueError(
                    "Cannot create Nutrient without required metadata: "
                    + ", ".join(missing_metadata)
                )

            created_id = (
                f"NUTRIENT:INFOODS_{tagname}"
                if tagname
                else nutrient_id
            )
            created = tx.run(
                """
                MERGE (n:Nutrient {id: $nutrient_id})
                ON CREATE SET
                    n.name = $name,
                    n.name_vi = $name_vi,
                    n.default_unit = $default_unit,
                    n.external_code = $tagname,
                    n.status = "active",
                    n.reviewed_at = toString(date()),
                    n.created_at = datetime(),
                    n.updated_at = datetime()
                ON MATCH SET
                    n.name = coalesce(n.name, $name),
                    n.name_vi = coalesce(n.name_vi, $name_vi),
                    n.default_unit = coalesce(n.default_unit, $default_unit),
                    n.external_code = coalesce(n.external_code, $tagname),
                    n.status = coalesce(n.status, "active"),
                    n.reviewed_at = coalesce(n.reviewed_at, toString(date())),
                    n.updated_at = datetime()
                RETURN n.id AS id,
                       n.name AS name
                """,
                nutrient_id=created_id,
                tagname=tagname or None,
                name=nutrient.get("infoods_name") or None,
                name_vi=nutrient.get("name_vi") or None,
                default_unit=nutrient.get("default_unit") or None
            ).single()

            tx.run(
                """
                MATCH (n:Nutrient {id: $nutrient_id})
                MERGE (a:Alias {
                    nutrient_id: n.id,
                    normalized_name: $normalized_name
                })
                ON CREATE SET
                    a.id = $alias_id,
                    a.name = $alias_name,
                    a.created_at = datetime()
                ON MATCH SET
                    a.name = coalesce(a.name, $alias_name),
                    a.updated_at = datetime()
                MERGE (a)-[:REFERS_TO]->(n)
                """,
                nutrient_id=created["id"],
                normalized_name=normalized_name,
                alias_id=Neo4jService._build_alias_id(
                    created["id"],
                    1
                ),
                alias_name=nutrient["name"]
            )

            return {
                "id": created["id"],
                "name": nutrient["name"],
                "value": nutrient.get("value"),
                "unit": nutrient.get("unit")
            }

        existing_id = existing["id"]
        existing_element_id = existing["element_id"]
        existing_name_vi = existing["name_vi"]

        name_vi_matches = (
            existing_name_vi
            and Neo4jService._normalize_text(existing_name_vi) == normalized_name
        )

        alias_exists = None

        if not name_vi_matches:
            alias_exists = tx.run(
                """
                MATCH (n:Nutrient)
                WHERE ($existing_id IS NOT NULL AND n.id = $existing_id)
                   OR ($existing_id IS NULL AND elementId(n) = $existing_element_id)
                MATCH (a:Alias)-[:REFERS_TO]->(n)
                WHERE a.normalized_name = $normalized_name
                   OR toLower(coalesce(a.name, "")) = $lower_name
                RETURN a
                LIMIT 1
                """,
                existing_id=existing_id,
                existing_element_id=existing_element_id,
                normalized_name=normalized_name,
                lower_name=nutrient["name"].strip().lower()
            ).single()

        if not name_vi_matches and not alias_exists:
            alias_count = tx.run(
                """
                MATCH (n:Nutrient)
                WHERE ($existing_id IS NOT NULL AND n.id = $existing_id)
                   OR ($existing_id IS NULL AND elementId(n) = $existing_element_id)
                OPTIONAL MATCH (existing_alias:Alias)-[:REFERS_TO]->(n)
                RETURN count(existing_alias) AS alias_count
                """,
                existing_id=existing_id,
                existing_element_id=existing_element_id
            ).single()["alias_count"]

            tx.run(
                """
                MATCH (n:Nutrient)
                WHERE ($existing_id IS NOT NULL AND n.id = $existing_id)
                   OR ($existing_id IS NULL AND elementId(n) = $existing_element_id)
                MERGE (a:Alias {
                    nutrient_id: coalesce(n.id, elementId(n)),
                    normalized_name: $normalized_name
                })
                ON CREATE SET
                    a.id = $alias_id,
                    a.name = $name,
                    a.created_at = datetime()
                ON MATCH SET
                    a.name = coalesce(a.name, $name),
                    a.updated_at = datetime()
                MERGE (a)-[:REFERS_TO]->(n)
                """,
                existing_id=existing_id,
                existing_element_id=existing_element_id,
                normalized_name=normalized_name,
                alias_id=Neo4jService._build_alias_id(
                    existing_id or existing_element_id,
                    alias_count + 1
                ),
                name=nutrient["name"]
            )

        return {
            "id": existing_id or existing_element_id,
            "name": nutrient["name"],
            "value": nutrient.get("value"),
            "unit": nutrient.get("unit")
        }

    @staticmethod
    def _build_alias_id(
        nutrient_id: str,
        sequence_number: int
    ) -> str:
        nutrient_suffix = nutrient_id.split("NUTRIENT:", 1)[-1]
        nutrient_suffix = re.sub(r"[^A-Z0-9_]+", "_", nutrient_suffix.upper())

        return f"ALIAS:{nutrient_suffix}_{sequence_number:02d}"

    @staticmethod
    def _sync_additive_tx(
        tx,
        additive: dict,
        ins: str
    ) -> dict:
        additive_id = Neo4jService._build_additive_id(ins)
        existing = tx.run(
            """
            OPTIONAL MATCH (a:Additive)
            WHERE toUpper(coalesce(a.ins, "")) = $ins
               OR a.id = $additive_id
            WITH collect(a)[0] AS additive
            RETURN
                additive.id AS id,
                elementId(additive) AS element_id,
                additive.name AS name,
                additive.name_vi AS name_vi,
                additive.ins AS ins
            LIMIT 1
            """,
            ins=ins,
            additive_id=additive_id
        ).single()

        if existing and existing["element_id"]:
            return {
                "id": existing["id"] or existing["element_id"],
                "name": additive.get("name"),
                "ins": existing["ins"] or ins
            }

        created = tx.run(
            """
            MERGE (a:Additive {id: $additive_id})
            ON CREATE SET
                a.ins = $ins,
                a.name = $name,
                a.name_vi = $name_vi,
                a.raw_page_number = $raw_page_number,
                a.raw_record_number = $raw_record_number,
                a.status = "active",
                a.reviewed_at = toString(date()),
                a.created_at = datetime(),
                a.updated_at = datetime()
            ON MATCH SET
                a.ins = coalesce(a.ins, $ins),
                a.name = coalesce(a.name, $name),
                a.name_vi = coalesce(a.name_vi, $name_vi),
                a.raw_page_number = coalesce(a.raw_page_number, $raw_page_number),
                a.raw_record_number = coalesce(a.raw_record_number, $raw_record_number),
                a.status = coalesce(a.status, "active"),
                a.reviewed_at = coalesce(a.reviewed_at, toString(date())),
                a.updated_at = datetime()
            RETURN
                a.id AS id,
                a.ins AS ins
            """,
            additive_id=additive_id,
            ins=ins,
            name=additive.get("name") or None,
            name_vi=additive.get("name_vi") or additive.get("name") or None,
            raw_page_number=additive.get("raw_page_number"),
            raw_record_number=additive.get("raw_record_number")
        ).single()

        return {
            "id": created["id"],
            "name": additive.get("name"),
            "ins": created["ins"]
        }

    @staticmethod
    def _build_additive_id(ins: str) -> str:
        suffix = re.sub(r"[^0-9A-Z]+", "_", ins.upper())
        suffix = suffix.strip("_")

        return f"ADDITIVE:INS_{suffix}"

    @staticmethod
    def _normalize_text(value: str) -> str:
        normalized = value.strip().lower()
        normalized = unicodedata.normalize("NFD", normalized)
        normalized = "".join(
            char
            for char in normalized
            if unicodedata.category(char) != "Mn"
        )
        normalized = normalized.replace("đ", "d")
        normalized = re.sub(r"[^a-z0-9]+", "_", normalized)
        normalized = normalized.strip("_")

        return normalized
