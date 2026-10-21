"""The object the `stores` fixture gives each contract test (contract-suite.md §1).

A `Server` is what a backend offers the suite beyond the protocols: more
store objects on the same server, a kill, and row counts read past the
protocols. The reference parameters are here; the Docker ones come with
their stores (T045, T065). `layout_module`, `row_counts`, `text_in_links`
and `vector_ids` are members the contract does not name (tasks.md T081).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from types import ModuleType
from typing import Final, Protocol

import pytest

from tenetrag.protocols import Collection, GraphStore, StepHook, VectorStore
from tests.support.contract.writes import COUNTED_TABLES
from tests.support.reference import ReferenceDatabase, ReferenceGraphStore, ReferenceVectorStore
from tests.support.reference import database as reference_database

REFERENCE_BACKENDS: Final = ("reference", "reference-split")


def index_id_for(node_id: str) -> str:
    """A fresh index id per test, so tests share a server without sharing rows."""
    return "t" + hashlib.sha256(node_id.encode()).hexdigest()[:12]


def writer_owner(backend: str) -> str:
    """The owner name under which the `stores` fixture holds the lease."""
    return f"contract:{backend}"


class Server(Protocol):
    @property
    def graph_writes_vectors(self) -> bool: ...
    @property
    def layout_module(self) -> ModuleType: ...
    def open_graph(self, index_id: str, step_hook: StepHook | None) -> GraphStore: ...
    def open_vectors(self, index_id: str) -> VectorStore: ...
    def kill_running_unit(self) -> None: ...
    def row_counts(self, index_id: str) -> dict[str, int]: ...
    def text_in_links(self, index_id: str) -> set[tuple[str, str, str]]: ...


@dataclass
class ContractStores:
    backend: str
    graph: GraphStore
    vectors: VectorStore
    graph_writes_vectors: bool
    index_id: str
    server: Server
    # Split only: the vector ids of each document's last write, step 1 of contract-suite.md §4.
    vector_ids: dict[str, dict[Collection, set[str]]] = field(default_factory=dict)

    def open_graph(
        self, *, index_id: str | None = None, step_hook: StepHook | None = None
    ) -> GraphStore:
        """Another store object on the same server; index_id=None means this test's index."""
        return self.server.open_graph(self._index(index_id), step_hook)

    def open_vectors(self, *, index_id: str | None = None) -> VectorStore:
        return self.server.open_vectors(self._index(index_id))

    def kill_running_unit(self) -> None:
        self.server.kill_running_unit()

    @property
    def layout_module(self) -> ModuleType:
        """The module whose `LAYOUT_VERSION` the store compares with the recorded one."""
        return self.server.layout_module

    def row_counts(self) -> dict[str, int]:
        """Rows of this index per table of data-model §6, keyed by `COUNTED_TABLES`."""
        return self.server.row_counts(self.index_id)

    def text_in_links(self) -> set[tuple[str, str, str]]:
        """Every `(entity_id, doc_id, attribute)` link of this index."""
        return self.server.text_in_links(self.index_id)

    def _index(self, index_id: str | None) -> str:
        return self.index_id if index_id is None else index_id


@dataclass(frozen=True)
class ReferenceServer:
    """Paired when the vectors live in the graph's database, split when in their own."""

    graph_db: ReferenceDatabase
    vector_db: ReferenceDatabase

    @property
    def graph_writes_vectors(self) -> bool:
        return self.vector_db is self.graph_db

    @property
    def layout_module(self) -> ModuleType:
        return reference_database

    def open_graph(self, index_id: str, step_hook: StepHook | None) -> GraphStore:
        paired = self.open_vectors(index_id) if self.graph_writes_vectors else None
        return ReferenceGraphStore(self.graph_db, index_id, vectors=paired, step_hook=step_hook)

    def open_vectors(self, index_id: str) -> ReferenceVectorStore:
        return ReferenceVectorStore(self.vector_db, index_id)

    def kill_running_unit(self) -> None:
        pytest.skip("the reference store has no server transaction to kill")

    def row_counts(self, index_id: str) -> dict[str, int]:
        with self.graph_db.lock:
            tables = self.graph_db.tables(index_id)
            return {name: len(getattr(tables, name)) for name in COUNTED_TABLES}

    def text_in_links(self, index_id: str) -> set[tuple[str, str, str]]:
        with self.graph_db.lock:
            return set(self.graph_db.tables(index_id).text_in)


def reference_stores(backend: str, index_id: str) -> ContractStores:
    """`reference`: vectors in the graph's database. `reference-split`: in their own."""
    if backend not in REFERENCE_BACKENDS:
        raise ValueError(f"no reference backend {backend!r}; use one of {REFERENCE_BACKENDS}")
    graph_db = ReferenceDatabase()
    vector_db = graph_db if backend == "reference" else ReferenceDatabase()
    server = ReferenceServer(graph_db=graph_db, vector_db=vector_db)
    return ContractStores(
        backend=backend,
        graph=server.open_graph(index_id, None),
        vectors=server.open_vectors(index_id),
        graph_writes_vectors=server.graph_writes_vectors,
        index_id=index_id,
        server=server,
    )
