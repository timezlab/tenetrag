"""Connections to Neo4j and Postgres (contracts/storage.md).

`open_connection` picks the class by `kind` and resolves the credential under
the connection's profile name. Each object holds one pool for one identity.
The drivers, behind the `neo4j` and `postgres` extras, are imported only when
a connection is opened. The graph and vector stores of M1 build on these.
"""

from __future__ import annotations

from typing import overload

from tenetrag.auth import Credential
from tenetrag.config import Neo4jSettings, PostgresSettings
from tenetrag.storage._shared import HealthReport
from tenetrag.storage.neo4j import Neo4jConnection
from tenetrag.storage.postgres import PostgresConnection

__all__ = ["HealthReport", "Neo4jConnection", "PostgresConnection", "open_connection"]


@overload
def open_connection(
    settings: Neo4jSettings, *, name: str, credential: Credential | None = None
) -> Neo4jConnection: ...
@overload
def open_connection(
    settings: PostgresSettings, *, name: str, credential: Credential | None = None
) -> PostgresConnection: ...
def open_connection(
    settings: Neo4jSettings | PostgresSettings, *, name: str, credential: Credential | None = None
) -> Neo4jConnection | PostgresConnection:
    """Open the connection the settings describe. `name` is its key under `connections`.

    A credential from code wins; otherwise the profile's named source is read.
    Opening does not check the server: call `health()` for that.
    """
    if isinstance(settings, Neo4jSettings):
        return Neo4jConnection(settings, name=name, credential=credential)
    return PostgresConnection(settings, name=name, credential=credential)
