"""The `stores` fixture: each contract test runs once per backend (contract-suite.md §1).

The Docker parameters join with their stores (T045, T065).
"""

import pytest

from tests.support.contract.backends import (
    REFERENCE_BACKENDS,
    ContractStores,
    index_id_for,
    reference_stores,
    writer_owner,
)
from tests.support.contract.writes import SCHEMA, VECTOR_SPEC

LEASE_TTL_S = 600


@pytest.fixture(params=REFERENCE_BACKENDS)
def stores(request: pytest.FixtureRequest) -> ContractStores:
    """A fresh index with the enterprise-docs schema, 8-dimension collections and the lease."""
    backend: str = request.param
    stores = reference_stores(backend, index_id_for(request.node.nodeid))
    stores.graph.ensure_schema(SCHEMA)
    stores.vectors.ensure_collections(VECTOR_SPEC)
    stores.graph.acquire_writer(writer_owner(backend), ttl_s=LEASE_TTL_S)
    return stores
