# Research: Domain packs and the synthetic corpus (M1, part 1)

Checked on 2026-10-12. This feature adds no package, so most of the work
was reading this repository and replaying one script. Labels:
**[source]** read in this repository's code or docs, **[run]** a script
run on 2026-10-12 in a scratch directory outside the repository,
**[session]** the record of the 2026-10-05 and 2026-10-06 design
sessions, **[inferred]** our reasoning.

## Versions and the dependency gate

No new dependency. Everything below is already locked by M0 (versions in
[001 research](../001-sdk-foundation/research.md#versions-and-the-dependency-gate)),
so the gate has nothing new to check.

| Need | Met by | Already locked as |
|---|---|---|
| Pack and case models, `extra="forbid"` | pydantic | base, 2.13.5 |
| Safe YAML with duplicate keys recorded | PyYAML, through M0's loader (R1) | base, 6.0.3 |
| Canonical JSON, SHA-256, NFC, regular expressions | `json`, `hashlib`, `unicodedata`, `re` | standard library |
| Reading shipped packs from the installed package | `importlib.resources` | standard library |
| Checking that a compiled schema is valid JSON Schema (tests only) | jsonschema, through `tenetrag.llm.structured.check_schema` | base, 4.26.0 |
| Corpus rendering | `str` templates in the generator (R12) | standard library |

Two candidates were rejected because the standard library is enough:
- **Jinja2** for corpus templates. The documents are short, and plain
  format strings keep the generator's output easy to trace to the fact
  table.
- **ruamel.yaml** for line numbers in every pack error. Problems name the
  path inside the pack (`entities.Person.vetoes[0]`), which is enough to
  find the line. Only duplicate keys carry a line, as in M0.

**Package data** [run]. `uv build --wheel` with hatchling 1.32.4 puts
`tenetrag/py.typed` in the wheel, so hatchling ships every non-ignored
file under `src/tenetrag`, not only `.py` files. The shipped YAML files
(R10) therefore need no build setting. A test lists the built wheel to
keep it so (quickstart §6).

## R0. Recovering the 60 identity design cases

- **Decision:** the cases come from replaying the original throwaway
  script, not from rewriting them. The replayed data is committed as a
  snapshot at
  [research/identity-design-cases.json](research/identity-design-cases.json),
  and the fixtures of R11 are converted from it.
- **How** [session]. The design sessions wrote `suite.py` once and then
  changed it with five patch scripts. All six were recovered from the
  session record and applied in order. The replay [run] reproduces every
  number ADR 0016 and the
  [identity criteria snapshot](../../docs/research/2026-10-05-entity-identity-criteria.md#9-the-suite)
  state:
  - wrong merges: R0 25, R1 11, R2 0;
  - R2: 58 correct, and 2 sent to the model with the right candidate
    offered (UNIT-9 and PER-7, as the snapshot names them);
  - 60 cases: 30 that must stay apart and 30 that must merge. Under R2,
    27 apart cases end as a new entity and 3 as `same_as` links (UNIT-3,
    UNIT-5, PER-1); 28 merge cases merge and 2 go to confirmation;
  - the minimality examples (UNIT-7, ORG-5, POL-3 and POL-4) and the
    over-specification table (PER-3, PER-2, POL-8, ORG-2, ORG-3, ORG-6).
- **What the snapshot holds:** the 31 entities, the 60 cases with their
  original Vietnamese titles, each case's R2 outcome, the R2 rule set,
  36 ablations (one rule element removed, and the cases that get worse)
  and 4 additions (a changeable attribute made a veto, and the cases it
  breaks).
- **One change from the original:** two emails used a domain that may be
  real. They now use the reserved `.example` domain (RFC 2606), per
  FR-041. The replay gives the same outcomes after the change.
- **Alternatives:** rewriting the cases from the snapshot's prose, which
  the spec allows as a fallback. Not needed, and a rewrite could not show
  that the R2 numbers still hold.

The script's own types differ from the packs'. R11 lists the conversion.

## R1. Where `tenetrag.packs` sits

- **Decision:**
  - `packs` is a sibling of `config` in the layers contract:
    `"llm | storage"`, `"auth"`, `"config | packs"`,
    `"protocols | _retry | _yaml"`.
  - A new private module, `tenetrag._yaml`, holds what both loaders need:
    the safe loader that records duplicate keys instead of keeping the
    last one, the parse function, and the YAML problem text that never
    repeats the input. These move unchanged out of
    `tenetrag/config/loading.py`, whose tests keep covering them.
  - `packs` imports the standard library, pydantic, PyYAML,
    `tenetrag.protocols` (for `ConfigError`) and `tenetrag._yaml`. A
    forbidden contract keeps it off the optional SDKs, as for `config`.
  - The engine (feature 004) may import `packs`. ARCHITECTURE.md already
    allows it.
- **Rationale:**
  - `config` and `packs` are independent: a profile names a pack, and a
    pack knows nothing of profiles. Neither has to import the other.
    The caller (the engine) loads the pack named by the profile and
    passes its hash to `stage_hashes` (R8).
  - The duplicate-key loader is knowledge that must not fork: a second
    copy could start keeping the last duplicate again.
- **Alternatives:**
  - `packs` above `config`, importing it: no use for it, and it would
    order two independent modules.
  - `packs` importing `tenetrag.config.loading`: crosses siblings, and
    `config.loading` is private.

## R2. Pack file format

- **Decision:** one pydantic model per part of the format of
  [domain-packs.md](../../docs/product/domain-packs.md#pack-format), with
  `extra="forbid"` and `frozen=True`, validating one file at a time. Every
  field of the format's table is accepted, including `deprecated`,
  `renamed_from`, `exact_mappings` and `agent_visible`, which this feature
  only stores. The rules the format leaves open:
  - **Names are ASCII identifiers.** Pack names are kebab-case. Entity,
    event, fact and enum names are `PascalCase`. Relation names are
    `UPPER_SNAKE`. Attribute, role and enum value names are
    `lower_snake`. They become JSON enum values, tool arguments, graph
    labels and SQL values, where non-ASCII names would need quoting and
    normalization. Text (descriptions, examples, aliases, glossary names
    and notes, question text) may be any Unicode, normalized to NFC.
  - **Reserved words.** An entity type cannot have an attribute named
    `scope`, an event type cannot have a role or attribute named `time`,
    and a fact type cannot have one named `issuer`. Each is a word of
    the identity or version-key grammar. `Definition`'s attribute `scope`
    is allowed, since facts have no entity scope.
  - **Delta fields are optional at file level.** Whether an entry is a
    new type or a change to an inherited one is known only after
    stacking, so every field may be absent in a file. R3 then requires
    `description` on every new entity, event and fact type. Relations
    and examples stay optional: the drafts give relation names that
    explain themselves, and examples only where they help. domain-packs.md
    is edited to say so (R13).
  - **Defaults, applied after stacking:** `mode` from the nearest
    ancestor (`core` sets `strict`); `names: key`; `scope.inherit: none`;
    `compare: text`; `unique: scope`; `extract: true`; relations
    `time` required; event types inherit `time` through `is_a`, and a
    root event type must state it; fact types default to `interval`.
  - **A pack file** needs `pack` and `version` (a positive integer). Only
    the shipped `core` may omit `extends`. A user pack whose name is a
    shipped pack's name fails.
- **Rationale:** the format is the user-facing contract. Validating the
  shape per file gives problems that name the file and path, before any
  merge.
- **Alternatives:** a JSON Schema for packs, validated with jsonschema.
  It would be a second definition of the same shape beside the models the
  stack needs anyway.

## R3. Stacking

- **Decision:**
  - **Linear order.** Depth-first over `extends` in listed order,
    post-order, each pack once: `[enterprise-docs, finance]` gives
    `core, enterprise-docs, finance, user`. A pack seen again on the
    current path is a cycle, and the error lists it
    (`user → a → user`).
  - **Deltas in order.** Each file is a delta over the packs before it.
    The merge records where every element came from, so a conflict names
    both packs.
  - **What a later pack may do** (domain-packs.md, stacking):

    | Element | Allowed change |
    |---|---|
    | types, relations, events, facts, enums | add new ones |
    | `attributes`, `roles` | add new ones; restating one identically is a no-op |
    | `from`, `to`, role types, `where` values, enum values | add values; the merged stack sorts them (R7) |
    | `identity` | add keys; a later pack's keys go in front of inherited ones |
    | `vetoes` | add |
    | `scope` | add `when` values; switch `inherit` from `none` to `document`; any other field it states must equal the inherited one |
    | `version_key` | append attributes |
    | `extract` | switch freely |
    | `not_entities`, `competency_questions` | union; question ids are unique |
    | `retrieval` | replace per key |
    | `mode` | the top pack's, else the nearest ancestor's |

  - **Everything else must be identical**, or it fails with a rule id:
    `stack.changed-range`, `stack.changed-time`,
    `stack.changed-description`, `stack.changed-identity` (`names`,
    `corroborate`, `version_start`, `compare`, `unique`, a scope's `role`
    or `to`), `stack.required-on-inherited`, `stack.removed` (a `null`
    or empty value that would remove an inherited element), and
    `stack.added-identity` (a scope, `corroborate` or `where` constraint
    added to an inherited type that had none, since it would tighten the
    type for every pack in the stack).
  - **Two parents** are merged into the linear order like any other
    packs. Two definitions of one element that differ fail with
    `stack.parents-conflict`, naming both packs. Identical ones merge
    silently.
  - **`is_a`** inherits roles, attributes and `time`. It does not inherit
    `identity`, `required` or `version_key`, since each event type merges
    on its own terms (ADR 0013).
- **Rationale:** one rule, "a child only adds", explains every row. It
  never loosens identity or tightens validation for other packs in the
  stack. Recording origins costs a map and makes every conflict
  actionable.
- **Alternatives:** C3 linearization, as in Python classes. It handles
  orders that depth-first gets wrong, but the merge does not depend on
  order beyond key priority, and a conflict fails anyway.

## R4. Problems and one `ConfigError`

- **Decision:**
  - Each problem is a
    `PackProblem(rule, file, path, message, severity)`. Loading runs in
    phases: each file (YAML, duplicate keys, shape), then the stack (the
    `extends` graph, the merge), then checks over the merged stack (R5).
  - A later phase runs even when an earlier one found problems. A
    definition with a problem is set aside, and its name still counts as
    defined, so a misspelt field does not also report every reference to
    that type.
  - A failed load raises one `ConfigError` listing every problem, one
    per line: `  - {file}: {path}: {message} [{rule}]`. Messages never
    repeat a YAML line, as in M0.
  - Warnings are kept on the stack (`stack.warnings`) and logged once at
    WARNING through the `tenetrag.packs` logger.
- **Rationale:** FR-010 asks for every problem at once. The rule id makes
  SC-003 testable: each broken test pack asserts its rule id.
- **Alternatives:** stopping at the first phase with problems. Simpler,
  but a pack author would fix problems one round at a time.

## R5. Checks after the merge

- **Decision**, run over the merged stack:
  - **References** (FR-007): every type, role, relation, attribute and
    enum a definition names exists; `is_a` names one existing type of the
    same kind; a `where` attribute is an enum on every allowed type of
    that endpoint; `version_key`, `document_link`, `corroborate`,
    `version_start`, `cardinality` and `during` name what the type has;
    a type name is used by one kind only.
  - **Identity lint** (FR-008), as listed in
    [domain-packs.md](../../docs/product/domain-packs.md#identity-fields),
    with rule ids `identity.key-needs-scope`, `identity.key-not-minimal`,
    `identity.veto-multivalued`, `identity.veto-range`,
    `identity.veto-is-name` (a veto named `name` or `title`) and
    `identity.versioned-needs-start`. `identity.evidence-without-corroborate`
    is a warning.
  - **Text lint** (FR-009, rule `text.instruction`). It reads every text
    a model sees: descriptions, examples, aliases, attribute
    descriptions, question text, and glossary names, aliases and notes.
    The patterns, matched as whole words after NFC and case folding:
    - English: `ignore`, `disregard`, `you must`, `you should`,
      `you are`, `system prompt`, `previous instructions`;
    - Vietnamese: `bỏ qua`, `bạn phải`, `bạn là`;
    - URLs: a `scheme://` or `www.`;
    - the agent tool names of engine brief §5 (`describe_schema`,
      `find_entities`, `get_entity`, `get_neighbors`, `get_sources`, and
      `retrieve(`).

    It warns, and fails when the stack's mode is `strict`. Since `core`
    is strict, a user pack on a shipped stack is strict unless it sets
    `mode: discovery`, so the patterns are kept narrow: whole words, no
    generic call syntax, which would flag "customer(s)".
  - **Glossary** (FR-012): allowed in user packs only, and the merged
    glossary is the union of theirs. A user file cannot pass for a
    shipped pack (R2), so a shipped pack with a glossary can only come
    from this repository, and a test on the shipped files rejects it.
    Each entry's type exists, and an alias maps to at most one entry per
    type.
  - **Coverage at load:** each competency question whose needs are
    missing or not extracted gives a warning (`coverage.unmet`), not an
    error (R9).
- **Rationale:** references are checked once, on the stack, because a
  name may be defined by any pack in it.

## R6. The compiled schema

- **Decision:** a fixed shape. Types, attribute names and role names
  grow enums, never keys.

  | Part | Properties |
  |---|---|
  | root: `entities`, `relations`, `events`, `facts` | 4 |
  | entity: `id`, `type`, `surface`, `is_name`, `name`, `translation`, `ref`, `scope`, `former_names`, `attributes` | 10 |
  | entity former name: `name`, `quote` | 2 |
  | entity attribute: `name`, `value`, `quote` | 3 |
  | relation: `type`, `from`, `to`, `attributes`, `valid_from`, `valid_to`, `quote` | 7 |
  | relation attribute | 3 |
  | event: `id`, `type`, `roles`, `attributes`, `valid_from`, `valid_to`, `quote` | 7 |
  | event role: `role`, `ref` | 2 |
  | event attribute | 3 |
  | fact: `type`, `roles`, `attributes`, `valid_from`, `valid_to`, `quote` | 6 |
  | fact role | 2 |
  | fact attribute | 3 |
  | **total** | **52** |

  - The entity fields follow engine brief §2.4. A relation's main
    `value` is the attribute named `value`. Events carry an `id`
    because a role may point to an event (`made_in`).
  - Every property is required, every object has
    `additionalProperties: false`, and an absent value is `""`. There
    are no null unions, since `anyOf` is forbidden. Date precision is
    the granularity of the ISO string (`2025`, `2025-03`, `2025-03-01`).
  - Enums are sorted: type names per kind, attribute names per kind (the
    union over the selected types, plus `value` for relations that
    declare one), role names per kind.
  - A part whose name set is empty is left out (a kind with no selected
    type, or an `attributes` list when no selected type has an
    attribute). An empty enum is meaningless, and `maxItems: 0` is not
    known to work on every provider.
  - `compile_schema(stack, types=None, max_properties=64)`. A subset
    names extractable types; an unknown name or an `extract: false` type
    in the subset is a `ConfigError`.
  - Output is serialized with sorted keys, compact separators and
    `ensure_ascii=False`, so the same stack gives the same bytes.
- **Prototype** [run]. A throwaway script built this shape over the
  union of all three drafts (`core`, `enterprise-docs`, `finance`): 52
  properties, enums of 12 entity, 17 relation, 6 event and 4 fact types,
  4,175 bytes. M0's `check_schema` accepted it under the Databricks
  profile (no `$ref`, `anyOf`, `oneOf`, `allOf`, `pattern` or
  `prefixItems`; at most 64 properties).
- **Consequence for the spec.** With a fixed shape no stack passes 64,
  so US2-2 cannot be met by "the definitions that add the most keys".
  The limit still guards providers with a lower one: a caller may pass
  `max_properties`, and the error lists the shape's parts by property
  count. FR-020 and US2-2 are reworded (R13).
- **Alternatives:** one property per attribute (`{"code": …}`) reads
  better for the model, but a 50-type stack passes 64 at once, and the
  domain-packs design already chose key and value lists.

## R7. Hashes and the stamp

- **Decision:** four hashes, each `"sha256:<hex>"` over canonical JSON
  as in M0 (`format` number, sorted keys, compact separators,
  `ensure_ascii=False`, `allow_nan=False`, NFC strings):

  | Hash | Covers | Used by |
  |---|---|---|
  | content hash | the whole merged stack, defaults filled in | the stamp (FR-024) |
  | index hash | the merged stack without `retrieval` and `glossary` | the extract and resolve stage hashes (R8) |
  | glossary hash | the merged glossary | the engine, per chunk (feature 004) |
  | file hash | one parsed pack file, NFC, without unset fields | the pin test of shipped versions (FR-016) |

  - Set-like lists are sorted in the merged stack itself (endpoint
    types, role types, vetoes, `required`, `where` values, enum values,
    `not_entities`, `corroborate`, `document_link`). Ordered lists keep
    their order: identity keys (tried in order), `version_start`,
    examples and aliases (prompt order). So reordering a set changes no
    hash, and the compiled schema is deterministic.
  - The content hash leaves out pack names, versions and where each
    element came from: two stacks with the same content have the same
    hash. The stamp carries the top pack's name and version beside it.
  - Competency questions, `mode` and descriptions stay in the index
    hash: the spec counts every pack change except retrieval hints and
    the glossary as an extraction change. Over-triggering a re-index is
    safe.
  - The pin test maps each shipped `(name, version)` to its file hash.
    A changed file with an unchanged version fails, saying "bump
    `version` in {file} and add a pin for the new version". Comment and
    layout changes leave the file hash alone.
- **Rationale:** the content hash cannot pin shipped versions, because
  a change to `core` would also change `enterprise-docs`'s stack hash,
  although its own file did not change.
- **Alternatives:** hashing the raw file bytes. Comments and whitespace
  would then force version bumps.

## R8. The profile names the pack; stage hashes take its hash

- **Decision:**
  - `Profile.pack: str = "core"`, marked `Operational()`. A value ending
    in `.yaml` or `.yml` is a path. Anything else is a shipped pack name
    matching `^[a-z][a-z0-9]*(-[a-z0-9]+)*$`; the profile checks only
    the syntax, and `load_pack` checks that the name exists.
  - `load_profile` rewrites a relative pack path to an absolute one
    against the profile file's directory. `profile_from_yaml` and
    `profile_from_dict` leave it as written, relative to the working
    directory.
  - `stage_hashes(profile, *, pack_hash: str)`. The argument is
    required, so no caller can forget the pack. It enters the `extract`
    and `resolve` fields as `pack`. The other stages are unchanged.
  - The golden hashes of M0's two fixture profiles change for `extract`
    and `resolve` only. `_FORMAT` stays 1: the field set changed, so old
    and new hashes cannot collide.
- **Rationale:**
  - The field holds a pointer, often a machine-specific path. Hashing
    the path would re-index after a move and miss an edit, so the field
    is operational and its content enters through `pack_hash`.
  - A required keyword fails closed. A default of "no pack" would let a
    caller build stage hashes that ignore the pack.
- **Alternatives:**
  - `config` loading the pack itself: `config` cannot import `packs`
    (R1), and the profile would then do file I/O for a second format.
  - Hashing the pack name and version only: a user pack edited without
    a version bump would not re-index.

## R9. Coverage

- **Decision:** `check_coverage(stack)` returns, per competency question,
  the needed names the stack lacks and those it defines with
  `extract: false`. A question passes when both lists are empty. A need
  names any type or relation. Loading also warns for each unmet question.
- **Spec tension:** FR-007 lists "a competency question" among the
  references loading must check, which would make an unknown need a load
  error. US3-2 then could never run, since the coverage check needs a
  loaded stack. The need is reported by coverage, and loading warns.
  FR-007 and FR-026 are reworded (R13).
- **Rationale:** a pack author writes questions before the types exist
  (step 3 of the design workflow). A failing load would block the very
  check that tells them what to add.

## R10. Shipped packs

- **Decision:**
  - `src/tenetrag/packs/shipped/core.yaml` and `enterprise-docs.yaml`,
    built from the drafts in `docs/product/packs/`, read through
    `importlib.resources`. Their identity cases sit beside them
    (`core.cases.yaml`, `enterprise-docs.cases.yaml`).
  - The drafts of `core` and `enterprise-docs` are deleted. domain-packs.md
    and v1-packs.md link to the shipped files (FR-015).
  - The `finance` draft stays at `docs/product/packs/finance.yaml` and
    extends the shipped `core` by name. Tests load it by path, alone and
    as `[enterprise-docs, finance]` (FR-019). Those tests need a
    repository checkout, which every CI job has.
  - Changes from the drafts, kept to what the loader requires: the
    "Draft, no code loads it" comment goes, and every new entity, event
    and fact type gets the `description` R3 requires if it lacks one.
    Each such change is listed in the commit.
- **Rationale:** one copy per pack (FR-015). Package data works in a
  wheel with only the base install (SC-011).
- **Alternatives:** packs as Python dicts in code. Pack authors read YAML,
  and the shipped packs are the examples they copy.

## R11. Identity cases

- **Decision:**
  - **Format.** One YAML file per stack, loaded and checked by
    `tenetrag.packs.cases` (data model §8):
    - `pack:` names the stack, as a shipped name or a path relative to
      the case file;
    - `entities:` are shared by id, each with type, name, aliases, scope
      (an entity id), attributes as `{value, quote}`, relations and
      former names;
    - `cases:` each has an id, `origin` (`design` or `added`), `expect`
      (`merge` or `apart`), a title, the existing entity ids, the
      mention, the outcome, `depends_on` and, when a veto keeps the pair
      apart, `blocked_by`.
  - **Elements a case depends on** are written `scope`,
    `key:scope+code`, `veto:code`, `names:versioned`, `unique:code` or
    `corroborate:MEMBER_OF`. The checker resolves each against the
    mention type in the case's stack, so `veto:employee_id` under `core`
    fails: `core`'s `Person` has no such veto.
  - **Converting the design cases** from the snapshot (R0):
    - `Company` becomes `Organization` with `category: company`, and
      `OrgUnit` becomes `Organization` with `category: unit` under
      `core`, or `department` or `branch` under `enterprise-docs`, as
      the case's title says;
    - the script's `unit_at` and `title_at` become `MEMBER_OF` and
      `HOLDS_POSITION` relations, which `Person` corroborates;
    - `renamed_from` becomes a former name, and the script's proposed
      name becomes the mention's translation;
    - `scope_exact: false` becomes `scope_source: document`. WRK-3 and
      PER-9 also get `document`, since their titles say the scope came
      from the document although the script's flag did not record it;
    - every attribute gets a synthetic quote;
    - `depends_on` comes from the ablations, and `blocked_by` from the
      veto that keeps an apart case apart;
    - the outcome comes from the R2 result: `MERGE` → merge into the
      expected entity, `NEW` → new, `LINK` → `same_as` with the
      candidates, `ASK` → confirm with the candidates and the right one.
  - **Stacks:**

    | Stack | Cases |
    |---|---|
    | `core` | ORG-1, 2, 3, 4, 7; UNIT-7, 11, 12; PER-1, 2, 3, 4, 6, 7; WRK-1, 2, 4, 5, 6; PRD-1; PLC-1; MET-1; CON-1 (23) |
    | `enterprise-docs` | UNIT-1, 2, 3, 4, 5, 6, 8, 9, 10, 13; PER-5, 8, 9; POL-1 to 12; WRK-3; PRJ-1, 2, 3; SYS-1 (30) |
    | `finance` draft, by path | ORG-5, ORG-6, INS-1 to 5 (7) |

    The `finance` cases live in `tests/fixtures/identity/`, since
    `finance` is not shipped. The spec assumed a test-only copy of the
    draft's `Instrument`. Loading the draft itself, as FR-019 already
    does, leaves nothing to drift; the assumption is reworded (R13).
  - **13 added cases**, so that FR-031 holds for both shipped packs:

    | Stack | Id | Expect | Element |
    |---|---|---|---|
    | `core` | PLC-2 | merge | same commune, same province (scope) |
    | `core` | PRD-2 | merge | same product, same provider (scope) |
    | `enterprise-docs` | PRD-3 | merge | provider inherited from the document |
    | `enterprise-docs` | PRD-4 | apart | provider inherited from another company's document |
    | `enterprise-docs` | WRK-7 | apart | same contract number, issuer inherited from another company |
    | `enterprise-docs` | SYS-2 | merge | same system name, same owner |
    | `enterprise-docs` | PROC-1 | apart | same title, another company (scope) |
    | `enterprise-docs` | PROC-2 | merge | `key:scope+code` |
    | `enterprise-docs` | PROC-3 | merge | `key:scope+title+version_label` |
    | `enterprise-docs` | PROC-4 | merge | `key:scope+title+issued_on` |
    | `enterprise-docs` | PROC-5 | apart | `veto:code` |
    | `enterprise-docs` | PROC-6 | apart | `veto:issued_on` |
    | `enterprise-docs` | PROC-7 | apart | `veto:version_label` |

  - **Coverage per shipped pack** (FR-031), with the cases above:

    | Pack | Type | Merge | Apart | Keys and vetoes, each with a case |
    |---|---|---|---|---|
    | `core` | Organization | ORG-2, 3, 4, UNIT-11 | ORG-1, 7, UNIT-7, 12 | key `[registration_id]` ORG-2, UNIT-11; veto `registration_id` ORG-1, ORG-7, UNIT-12; veto `established_on` UNIT-7 |
    | `core` | Person | PER-2, 3, 4, 7 | PER-1, 6 | key `[email]` PER-3, PER-4 |
    | `core` | Place | PLC-2 | PLC-1 | none declared |
    | `core` | Work | WRK-1, 6 | WRK-2, 4, 5 | key `[scope, code]` WRK-6; veto `code` WRK-4; veto `issued_on` WRK-5 |
    | `core` | Product | PRD-2 | PRD-1 | none declared |
    | `enterprise-docs` | Organization (scope changed) | UNIT-4, 6, 8, 9, 13 | UNIT-1, 2, 3, 5, 10 | none declared |
    | `enterprise-docs` | Person (changed) | PER-8, 9 | PER-5 | key `[scope, employee_id]` PER-8; veto `employee_id` PER-5 |
    | `enterprise-docs` | Work (scope changed) | WRK-3 | WRK-7 | none declared |
    | `enterprise-docs` | Product (scope changed) | PRD-3 | PRD-4 | none declared |
    | `enterprise-docs` | Policy | POL-3, 4, 6, 8, 9, 10 | POL-1, 2, 5, 7, 11, 12 | keys POL-6, POL-9, POL-10; vetoes `code` POL-12, `version_label` POL-11, `issued_on` POL-7 |
    | `enterprise-docs` | Procedure | PROC-2, 3, 4 | PROC-1, 5, 6, 7 | keys PROC-2, 3, 4; vetoes PROC-5, 6, 7 |
    | `enterprise-docs` | Project | PRJ-2 | PRJ-1, 3 | key PRJ-2; veto `code` PRJ-3 |
    | `enterprise-docs` | System | SYS-2 | SYS-1 | none declared |

    That gives 73 cases: 60 from the design and 13 added. `Metric` and
    `Concept` declare no identity field, so FR-031 does not ask for
    their cases. MET-1 and CON-1 still run.
  - **The D5 situation** (US4-5) is POL-1 and UNIT-1: Beta's
    same-titled policy and same-named unit stay apart from Alpha's. The
    metric itself merges across companies (MET-1), since `Metric` has no
    scope. The two companies' limits on it are `Requirement` facts, and
    facts are not resolved like entities: they are grouped by
    `version_key`, which includes the issuer, so D5's limit sits in its
    own version group. That pair is stated by the corpus (R12), not by an
    identity case. US4-5 is reworded to say so (R13).
  - **The check** (FR-032) runs in the unit tests: every type,
    attribute, relation and element a case names exists in its stack;
    entity ids resolve; quotes are non-empty; outcome ids are among the
    existing entities; FR-031 holds per shipped pack. It runs no
    resolver. Feature 004 runs the cases through the engine.
- **Rationale:** cases written in the pack's own vocabulary are what the
  resolver reads in feature 004, and the checker catches a case that a
  pack change has made meaningless.
- **Alternatives:** keeping the cases in the script's own types, mapped
  at run time. The cases would then never be checked against a pack.

## R12. The corpus generator

- **Decision:**
  - **Where.** The generator is test support, not SDK code:
    `tests/support/corpus/`, run as
    `uv run python -m tests.support.corpus` (with `--check` in CI). Its
    input is the fact table under `tests/fixtures/corpus/facts/`, and its
    output goes to `tests/fixtures/corpus/generated/` and is committed
    (FR-040).
  - **The fact table** (YAML, data model §9) holds:
    - the world: organizations, units, people, policies, metrics and
      the other entities, each with a stable id;
    - documents: id, language, issuer, title, format label, the dates
      the text states, and their content as blocks. A block is a
      heading, a paragraph, a list or a table. Its sentences are written
      in the fact table, in the document's language, and each item a
      sentence states gives the exact quote;
    - items: each expected entity mention, relation, event and fact, with
      its world ids, attributes and quote;
    - the graph results that cannot be derived by a simple rule: deletion
      scenarios and `TEXT_IN` links;
    - hand-written golden questions.
  - **The generator:**
    - renders each document to Markdown (`D1.md` …), NFC, LF line
      endings, Vietnamese number and date formats in the text;
    - checks that every item's quote occurs in its document's rendered
      text, and fails naming the document and the item (FR-039);
    - checks that every item fits the shipped stack: type, roles,
      attributes, required fields, endpoint types (FR-039). The check is
      small and local to the generator; feature 004's validator may later
      replace it;
    - derives the graph results that follow a rule: mentions with one
      world id are one entity; version statuses and supersession by
      engine brief §3.2 (newest `current`, older `superseded` with
      `closed_at`, same start `conflicting`);
    - writes golden questions from templates per question type over the
      fact table, then appends the hand-written ones after checking that
      every source they cite exists.
  - **Running example.** D1 to D5 are written in the fact table word for
    word from the engine brief, with the brief's dates and owners. A test
    pins by hand what the derivation must give: r1 `superseded` with
    `closed_at` 2026-01-15, r2 `current`, D5's limit in its own group,
    and r1 `current` again after deleting D2. So a wrong derivation
    fails a test written apart from the generator.
  - **Size.** About 40 documents: at least 12 in Vietnamese, 12 in
    English and 4 mixed, which leaves room above FR-033's floors.
  - **Golden set.** One JSONL file, one question per line, with the
    benchmark's fields: `question`, `expected_answer`,
    `expected_sources` (document ids) and `tags`. Tags are strings:
    `id`, `qtype` (the eight types of
    [test-corpora.md](../../docs/reference/test-corpora.md#why-this-page-exists)),
    `lang`, `cq` (comma-separated question ids), `as_of` and `origin`
    (`generated` or `hand_written`). test-corpora.md planned one file per
    question type; one file filtered by `qtype` is simpler for the
    benchmark and is recorded there (R13).
  - **Determinism.** No clock, no randomness, no set iteration: every
    collection is sorted or kept in fact-table order. JSON is written
    with sorted keys. The CI check regenerates into a temporary
    directory and compares bytes with the committed files.
- **Rationale:** sentences written by hand read like real documents; a
  generator that composed every sentence from fragments would plant
  answers in stilted text. The generator's job is the part a person gets
  wrong: quotes that drift from the text, items that no longer fit the
  pack, and answers that must follow from dates.
- **Alternatives:**
  - a model writing the documents: not reproducible, and the corpus must
    be byte-identical on every run (FR-033);
  - Faker for names: a new dependency, and fixed fictional names are
    easier to review for FR-041.

## R13. Spec edits made with this plan

Small wording changes, with the reason in the section named:
- FR-007: "a competency question" is removed from the references that
  fail a load. FR-026 adds that loading warns about each unmet question
  (R9).
- FR-020 and US2-2: a stack past the limit fails with the count and the
  parts of the schema that hold the most properties. The limit is a
  parameter, 64 by default (R6).
- Assumptions and the matching edge case: the design cases for
  `Instrument` run under the `finance` draft loaded by path, not under a
  test-only copy (R11).
- US4-5: the two companies' policies and units stay apart as identity
  cases; their metric is one entity, and their limits are kept apart by
  version key in the corpus (R11).
- domain-packs.md (with the code, FR-043): new entity, event and fact
  types need a description; examples are optional (R2).
- test-corpora.md (with the code, FR-043): tier 1 lives in
  `tests/fixtures/corpus/`, with one golden JSONL file (R12).

## Notes for later features

- **Store, feature 003.** `Decision` and `ActionItem` have an attribute
  named `status`, and every event and fact also has the engine-owned
  `status` (`current`, `superseded`, `conflicting`). A store must keep
  pack attributes apart from engine fields.
- **Engine, feature 004.** The compiled schema's attribute values are
  strings. Validation parses each into its range (`date`, `int`, an enum
  value) and drops it with `BAD_VALUE` when it does not parse.
- **Open questions** of domain-packs.md stay open: Vietnamese aliases in
  packs, types per extraction pass, and enum caps in provider schemas.
  The largest stack's biggest enum is 23 attribute names (R6), far from
  any cap seen so far.
