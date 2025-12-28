from __future__ import annotations

import os
from dataclasses import dataclass
from neo4j import GraphDatabase


@dataclass(frozen=True)
class Neo4jConfig:
    uri: str
    user: str
    password: str


def load_neo4j_config_from_env() -> Neo4jConfig:
    uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    user = os.getenv("NEO4J_USER", "neo4j")
    password = os.getenv("NEO4J_PASSWORD", "password")
    return Neo4jConfig(uri=uri, user=user, password=password)


class Neo4jClient:
    _driver = None

    def __init__(self, cfg: Neo4jConfig):
        self.cfg = cfg
        if Neo4jClient._driver is None:
            Neo4jClient._driver = GraphDatabase.driver(
                cfg.uri,
                auth=(cfg.user, cfg.password),
            )
        self._driver = Neo4jClient._driver

    def close(self) -> None:
        # KHÔNG close driver trong request
        pass


    def run_write(self, cypher: str, params: dict | None = None) -> None:
        params = params or {}
        with self._driver.session() as session:
            session.execute_write(lambda tx: tx.run(cypher, **params))

    def run_read(self, cypher: str, params: dict | None = None):
        params = params or {}
        with self._driver.session() as session:
            return session.execute_read(lambda tx: list(tx.run(cypher, **params)))
