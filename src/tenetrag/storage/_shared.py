"""What the Neo4j and Postgres connections share: the health report and host checks."""

from __future__ import annotations

import ipaddress
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True, slots=True)
class HealthReport:
    """What `health()` found (data-model §7). Returned only when the server meets the floors."""

    backend: Literal["neo4j", "postgres"]
    server_version: str
    edition: str | None  # Neo4j only
    extensions: Mapping[str, bool]  # Postgres only: name -> available
    identity: str
    encrypted: bool


def is_local_host(host: str) -> bool:
    """`localhost` or a loopback address, where `auto` TLS allows a plain connection."""
    if host.lower() == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def address(host: str, port: int) -> str:
    """`host:port` for messages, with an IPv6 address in brackets."""
    return f"[{host}]:{port}" if ":" in host else f"{host}:{port}"
