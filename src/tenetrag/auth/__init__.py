"""Credentials that fail closed: passed in code or named in the profile (contracts/auth.md).

There is no fallback to another identity (ADR 0003). The Databricks kinds that
delegate to the Databricks SDK need the `databricks` extra.
"""

from tenetrag.auth.credentials import AccessToken, Credential, CredentialKind, Credentials, Secret
from tenetrag.auth.resolve import ACCEPTED_KINDS, TargetKind, resolve_credential

__all__ = [
    "ACCEPTED_KINDS",
    "AccessToken",
    "Credential",
    "CredentialKind",
    "Credentials",
    "Secret",
    "TargetKind",
    "resolve_credential",
]
