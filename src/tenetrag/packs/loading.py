"""Loading a pack stack: references, files, stacking and checks (data-model §1, research R4).

Private to `tenetrag.packs`; `load_pack` and `shipped_packs` are exported
from the package. Each phase collects its problems. Reading stops after the
reference and file phases when a file could not be read or a reference is
wrong, since stacking a partial stack would only add noise; otherwise the
stack is merged and checked, and every error is raised together.
"""

from __future__ import annotations

import dataclasses
import logging
import os
from collections.abc import Sequence
from dataclasses import dataclass, field
from importlib import resources
from importlib.resources.abc import Traversable
from pathlib import Path
from typing import Any

import yaml

from tenetrag._yaml import parse_yaml, yaml_problem
from tenetrag.packs.checks import check_stack
from tenetrag.packs.format import PACK_NAME, ParsedPack, parse_pack
from tenetrag.packs.hashing import file_hash, stamped
from tenetrag.packs.problems import PackProblem, config_error
from tenetrag.packs.stack import PackInfo, PackStack, ShippedPack
from tenetrag.packs.stacking import PackFile, stack_files
from tenetrag.protocols.errors import ConfigError

# The package's logger rather than this module's, so callers configure one name
# (contracts/packs.md).
logger = logging.getLogger("tenetrag.packs")

_SHIPPED = "shipped"
_SUFFIXES = (".yaml", ".yml")
# A file with one of these problems has no content to stack.
_UNLOADED = frozenset(
    {"file.unreadable", "file.not-utf8", "file.yaml", "file.empty", "file.not-mapping"}
)


def shipped_packs() -> tuple[ShippedPack, ...]:
    """The packs shipped inside tenetrag.packs, sorted by name."""
    packs = []
    for name in _shipped_names():
        data, _ = parse_yaml(_shipped_file(name).read_text(encoding="utf-8"))
        version = data.get("version") if isinstance(data, dict) else None
        if not isinstance(version, int):
            raise ConfigError(f"The shipped pack {name} has no version. Reinstall tenetrag.")
        packs.append(ShippedPack(name, version))
    return tuple(packs)


def load_pack(
    reference: str | os.PathLike[str],
    *,
    base_dir: str | os.PathLike[str] | None = None,
) -> PackStack:
    """Load a shipped pack by name, or a pack file by path, with every pack it extends.

    Raises `ConfigError` listing every error. Warnings are returned on
    `PackStack.warnings` and logged once each.
    """
    loader = _Loader(Path(base_dir) if base_dir is not None else Path.cwd())
    label = os.fspath(reference)
    target = loader.resolve(label, label, "", None)
    if target is not None:
        loader.visit(target, [])
    problems = loader.problems
    if any(problem.rule in _UNLOADED or problem.rule.startswith("pack.") for problem in problems):
        raise config_error(problems)
    files = loader.files()
    stacked = stack_files(files)
    problems = [*problems, *stacked.problems, *check_stack(stacked, files)]
    if any(problem.severity == "error" for problem in problems):
        raise config_error(problems)
    for warning in problems:
        logger.warning(
            "Pack %s: %s: %s [%s]", warning.file, warning.path, warning.message, warning.rule
        )
    return stamped(dataclasses.replace(stacked.stack, warnings=tuple(problems)))


@dataclass(frozen=True, slots=True)
class FileKind:
    """The messages a file problem gives for one kind of YAML file: a pack or a case file."""

    empty: str
    not_mapping: str


PACK_FILE = FileKind(
    empty="the file is empty; write a pack in it",
    not_mapping="a pack is a mapping of fields such as `pack:` and `entities:`",
)


def read_mapping(
    source: Path | Traversable, label: str, kind: FileKind
) -> tuple[dict[Any, Any] | None, list[PackProblem]]:
    """A file's top mapping, read safely, with its file.* problems; None when it has no mapping.

    A repeated key is a problem, yet the mapping is still returned, so that
    the rest of the file is checked in the same pass. `label` names the file.
    """
    problems: list[PackProblem] = []

    def problem(rule: str, path: str, message: str) -> None:
        problems.append(PackProblem(rule, label, path, message, "error"))

    try:
        raw = source.read_bytes()
    except OSError as exc:
        reason = exc.strerror or type(exc).__name__
        problem(
            "file.unreadable",
            "",
            f"cannot read the file: {reason}; check that the path names a readable file",
        )
        return None, problems
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        problem(
            "file.not-utf8", "", f"the file is not UTF-8 text (byte {exc.start}); save it as UTF-8"
        )
        return None, problems
    try:
        data, duplicates = parse_yaml(text)
    except yaml.YAMLError as exc:
        problem(
            "file.yaml",
            "",
            f"{yaml_problem(exc)}; fix the syntax, and use no tag that builds a Python object",
        )
        return None, problems
    for duplicate in duplicates:
        problem(
            "file.duplicate-key",
            duplicate.path,
            f"`{duplicate.key}` appears twice, at line {duplicate.line} "
            f"(first at line {duplicate.first_line})",
        )
    if data is None:
        problem("file.empty", "", kind.empty)
        return None, problems
    if not isinstance(data, dict):
        problem("file.not-mapping", "", kind.not_mapping)
        return None, problems
    return data, problems


@dataclass(frozen=True, slots=True)
class _Target:
    """A file a reference names. `key` tells two references to one file apart from two files."""

    key: str
    label: str
    shipped: str | None = None
    path: Path | None = None


@dataclass(slots=True)
class _Node:
    target: _Target
    parsed: ParsedPack
    parents: list[str] = field(default_factory=list)


class _Loader:
    def __init__(self, base_dir: Path) -> None:
        self.base_dir = base_dir
        self.shipped = _shipped_names()
        self.problems: list[PackProblem] = []
        self.nodes: dict[str, _Node] = {}
        # Post-order of the extends graph: every pack after the packs it extends.
        self.order: list[str] = []

    def problem(self, rule: str, label: str, path: str, message: str) -> None:
        self.problems.append(PackProblem(rule, label, path, message, "error"))

    def resolve(
        self, reference: str, label: str, path: str, referrer: _Target | None
    ) -> _Target | None:
        """The file `reference` names; `label` and `path` place the reference for a problem."""
        if reference.endswith(_SUFFIXES):
            if referrer is None:
                resolved = (self.base_dir / reference).resolve()
                return _Target(str(resolved), reference, path=resolved)
            if referrer.path is None:
                self.problem(
                    "pack.bad-reference", label, path, "a shipped pack extends shipped packs only"
                )
                return None
            child = os.path.normpath(os.path.join(os.path.dirname(referrer.label), reference))
            resolved = (referrer.path.parent / reference).resolve()
            return _Target(str(resolved), child, path=resolved)
        if PACK_NAME.fullmatch(reference):
            if reference in self.shipped:
                return _Target(f"{_SHIPPED}:{reference}", reference, shipped=reference)
            names = ", ".join(self.shipped)
            self.problem(
                "pack.unknown", label, path, f"no shipped pack has this name; use one of {names}"
            )
            return None
        self.problem(
            "pack.bad-reference",
            label,
            path,
            "a reference is a shipped pack name or a path ending in .yaml or .yml",
        )
        return None

    def visit(self, target: _Target, trail: list[_Target]) -> str | None:
        """Read `target` and the packs it extends, depth first; return its key if it loaded."""
        if target.key in self.nodes:
            return target.key
        parsed = self.read(target)
        if parsed is None:
            return None
        node = _Node(target, parsed)
        self.nodes[target.key] = node
        self.pack_problems(target, parsed)
        on_path = [*trail, target]
        for reference, path in parsed.extends:
            parent = self.resolve(reference, target.label, path, target)
            if parent is None:
                continue
            keys = [step.key for step in on_path]
            if parent.key in keys:
                cycle = [step.label for step in on_path[keys.index(parent.key) :]]
                self.problem(
                    "pack.cycle",
                    target.label,
                    path,
                    f"`extends` comes back to a pack on its own path: {' → '.join(cycle)} → "
                    f"{cycle[0]}; remove one of the references",
                )
                continue
            parent_key = self.visit(parent, on_path)
            if parent_key is not None:
                node.parents.append(parent_key)
        self.order.append(target.key)
        return target.key

    def read(self, target: _Target) -> ParsedPack | None:
        """One file's content, or None with a problem when it has none to stack."""
        label = target.label
        source = _shipped_file(label) if target.path is None else target.path
        data, problems = read_mapping(source, label, PACK_FILE)
        self.problems.extend(problems)
        if data is None:
            return None
        parsed, problems = parse_pack(data, label)
        self.problems.extend(problems)
        if any(problem.rule == "file.yaml" for problem in problems):
            return None
        return parsed

    def pack_problems(self, target: _Target, parsed: ParsedPack) -> None:
        if not parsed.has_extends and target.shipped != "core":
            self.problem(
                "pack.no-extends",
                target.label,
                "extends",
                "every pack extends another; add `extends: core` or a pack built on it",
            )
        if target.shipped is None and parsed.name in self.shipped:
            self.problem(
                "pack.shadows-shipped",
                target.label,
                "pack",
                "a shipped pack has this name; give the pack a name of its own",
            )

    def files(self) -> list[PackFile]:
        """The packs in linear order, top pack last, each with every pack it extends."""
        index = {key: position for position, key in enumerate(self.order)}
        ancestors: dict[str, frozenset[int]] = {}
        files = []
        for key in self.order:
            node = self.nodes[key]
            inherited: set[int] = set()
            for parent in node.parents:
                inherited |= {index[parent]} | ancestors[parent]
            ancestors[key] = frozenset(inherited)
            target = node.target
            source = _SHIPPED if target.shipped is not None else target.key
            parsed = node.parsed
            info = PackInfo(parsed.name or "", parsed.version or 0, source, file_hash(parsed))
            files.append(PackFile(target.label, node.parsed, info, ancestors[key]))
        return files


def shipped_directory() -> Traversable:
    """The package data holding the shipped packs and their identity case files."""
    return resources.files("tenetrag.packs") / _SHIPPED


def _shipped_file(name: str) -> Traversable:
    return shipped_directory() / f"{name}.yaml"


def _shipped_names() -> Sequence[str]:
    """The shipped pack names, sorted; a `.cases.yaml` file holds identity cases, not a pack."""
    names = (
        entry.name.removesuffix(".yaml")
        for entry in shipped_directory().iterdir()
        if entry.name.endswith(".yaml") and not entry.name.endswith(".cases.yaml")
    )
    return sorted(names)
