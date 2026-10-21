"""The engine: chunk, extract, resolve, version and retrieve, written against protocols.

It arrives in feature 004. Feature 003 adds only the text normalization the
stores and fixtures share (specs/003-stores-and-contract-suite/contracts/text.md).
The engine imports `tenetrag.protocols`, `tenetrag.config`, `tenetrag.packs` and
the standard library, and nothing else (ARCHITECTURE.md).
"""
