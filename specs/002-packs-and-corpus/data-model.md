# Data model: Domain packs and the synthetic corpus (M1, part 1)

The shapes feature 002 defines, with their validation rules. Names here
are public unless marked private (`_name`). The reasons are in
[research.md](research.md), and call signatures are in
[contracts/](contracts/).

## 1. Problems and rule ids

A pack problem is one frozen value:

```
PackProblem(rule: str, file: str, path: str, message: str, severity: "error" | "warning")
```

- `file` is a shipped pack's name (`core`) or a user file's path as the
  reference gave it. `path` is the dotted place inside the pack, such as
  `entities.Person.vetoes[1]`, or `""` for the whole file.
- A failed load raises one `ConfigError` (M0's class) whose message has a
  first line saying how many problems were found, then one line per
  error: `  - {file}: {path}: {message} [{rule}]`. Warnings are not in
  the error; they are on `PackStack.warnings` and logged once at WARNING
  by the `tenetrag.packs` logger.
- Messages say what to change. They never repeat a YAML line (M0's rule:
  a mistaken file may hold anything).

Every rule id has a broken test pack under
`tests/fixtures/packs/broken/<rule>/` (SC-003):

| Phase | Rule id | Fails when |
|---|---|---|
| reference | `pack.bad-reference` | a profile or `extends` value is neither a pack name nor a `.yaml`/`.yml` path |
| reference | `pack.unknown` | no shipped pack has that name |
| reference | `pack.cycle` | `extends` comes back to a pack on the current path; the message lists the cycle |
| reference | `pack.no-extends` | a pack other than the shipped `core` has no `extends` |
| reference | `pack.shadows-shipped` | a user file's `pack` name is a shipped pack's name |
| file | `file.unreadable` | the file cannot be read |
| file | `file.not-utf8` | the file is not UTF-8 |
| file | `file.yaml` | the YAML is invalid, or has a tag that would build an object |
| file | `file.duplicate-key` | a mapping repeats a key; the message gives both lines |
| file | `file.empty` / `file.not-mapping` | the file is empty, or its top level is not a mapping |
| file | `file.unknown-field` | a field the format lacks, such as `vetos` |
| file | `file.invalid-value` | a missing required field, or a value of the wrong type or outside its choices |
| file | `file.bad-name` | a name breaks the naming rules of §2 |
| file | `file.reserved-name` | an entity attribute named `scope`, an event role or attribute named `time`, a fact role or attribute named `issuer` |
| stack | `stack.missing-description` | a new entity, event or fact type has no `description` |
| stack | `stack.changed-range` | an inherited attribute's `range`, or a relation's `value`, changes |
| stack | `stack.changed-time` | an inherited type's `time` changes |
| stack | `stack.changed-description` | an inherited description changes (restating it word for word is fine) |
| stack | `stack.changed-identity` | an inherited `names`, `corroborate`, `version_start`, `compare`, `unique`, scope `role` or `to` changes, or `inherit` goes from `document` to `none` |
| stack | `stack.added-identity` | a scope, `corroborate` or `where` constraint is added to an inherited type or relation that had none |
| stack | `stack.required-on-inherited` | a pack adds `required` (a list entry or `required: true`) to a type another pack defined |
| stack | `stack.removed` | a `null` or empty value would remove an inherited element |
| stack | `stack.changed` | any other change to an inherited field, such as `is_a`, `cardinality`, `multivalued` or `unit` |
| stack | `stack.parents-conflict` | two parents define one element differently; both packs are named |
| stack | `stack.duplicate-question` | two competency questions share an id and differ |
| check | `ref.unknown` | a definition names a type, role, relation, attribute or enum that the stack lacks |
| check | `ref.is-a` | `is_a` names no type, a type of another kind, or makes a loop |
| check | `ref.where-not-enum` | a `where` attribute is not an enum on every allowed type of its endpoint |
| check | `ref.kind-clash` | one name is used by two kinds, such as an entity and a fact both called `Policy` |
| check | `identity.key-needs-scope` | a key of a scoped type holds an attribute with `unique: scope` but not `scope` |
| check | `identity.key-not-minimal` | one key of a type contains another key of that type |
| check | `identity.veto-multivalued` | a veto attribute is `multivalued` |
| check | `identity.veto-range` | a veto's range is not `str`, `date` or `int` |
| check | `identity.veto-is-name` | a veto is `name` or `title` |
| check | `identity.versioned-needs-start` | `names: versioned` has no `version_start` |
| check | `glossary.alias-clash` | one alias maps to two glossary entries of the same type |

Warnings, which never fail a load except as noted:

| Rule id | Raised when |
|---|---|
| `identity.evidence-without-corroborate` | `names: evidence` has no `corroborate`; every shared name then goes to the model |
| `text.instruction` | model-visible text reads like an instruction (research R5). An error when the stack's mode is `strict` |
| `coverage.unmet` | a competency question needs a name the stack lacks or does not extract (§6) |

## 2. Pack file

One YAML file, validated alone by the pydantic models in
`tenetrag/packs/format.py`: `extra="forbid"`, `frozen=True`, strict
types. Every string is normalized to NFC before validation. A field
marked "delta" may be absent when the entry changes an inherited
definition; §4 decides whether its absence is allowed.

**Names** (`file.bad-name`):

| Name | Pattern |
|---|---|
| pack | `^[a-z][a-z0-9]*(-[a-z0-9]+)*$` |
| entity, event, fact and enum types | `^[A-Z][A-Za-z0-9]*$` |
| relation types | `^[A-Z][A-Z0-9]*(_[A-Z0-9]+)*$` |
| attributes, roles, enum values, question ids' parts | `^[a-z][a-z0-9]*(_[a-z0-9]+)*$` |
| competency question ids | `^[a-z][a-z0-9]*(-[a-z0-9]+)*$` |

**Top level:**

| Field | Type | Notes |
|---|---|---|
| `pack` | pack name | required |
| `version` | int ≥ 1 | required |
| `extends` | reference or list of references | required except in the shipped `core` |
| `mode` | `strict` \| `discovery` | optional; §3 says how the stack gets one |
| `entities`, `events`, `facts` | map of type name → definition | optional |
| `relations` | map of relation name → definition | optional |
| `enums` | map of enum name → list of values | optional; values unique in the list |
| `not_entities` | list of `lower_snake` kinds | optional |
| `retrieval` | `Retrieval` | optional |
| `glossary` | list of `GlossaryEntry` | optional; user packs only |
| `competency_questions` | list of `CompetencyQuestion` | optional; required of shipped packs by a test |

A reference is a shipped pack name, or a path ending in `.yaml` or
`.yml`, relative to the file that holds it.

**`AttributeDef`:**

| Field | Type | Default after stacking |
|---|---|---|
| `range` | `str` `date` `money` `percentage` `int` `float` `bool`, or an enum name | required on a new attribute |
| `required` | bool | false |
| `multivalued` | bool | false |
| `unit` | str | none |
| `description` | text | none |
| `compare` | `text` `code` `digits` `lower` `upper` `date` | `text` |
| `unique` | `scope` `global` `self_scoped` | `scope` |

**`ScopeDef`** (delta): `role` (`lower_snake`), `to` (list of entity
types), `inherit` (`none` \| `document`), `when` (map of attribute → list
of enum values). A new scope needs `role` and `to`; `inherit` defaults to
`none`.

**Identity key:** a list of attribute names, where the literal `scope`
stands for the entity's scope, or `{key: [...], during: [start, end]}`
for a key that holds only between two date attributes.

**`EntityDef`** (all fields delta): `description`, `examples`, `aliases`,
`attributes`, `scope`, `identity` (list of keys), `vetoes`, `names`
(`key` \| `evidence` \| `versioned` \| `none`), `corroborate` (relation
names), `version_start` (date attributes), `document_link` (attributes),
`required`, `extract`, `agent_visible`, `exact_mappings`, `deprecated`,
`renamed_from`.

**`RelationDef`** (delta): `description`, `from`, `to` (entity types),
`where` (`{from|to: {attribute: [values]}}`), `time` (`none` \| `point`
\| `interval`), `attributes`, `value` (a range), `cardinality`
(`{one_at_a_time: [subject] | [subject, object] | [object]}`),
`required`, `extract`, `exact_mappings`, `deprecated`, `renamed_from`.

**`EventDef`** (delta): `description`, `examples`, `aliases`, `is_a`,
`roles` (role → list of entity or event types), `attributes`, `time`,
`identity` (list of entries; each a list of roles, attributes and
`time`), `required`, `extract`, `agent_visible`, `exact_mappings`,
`deprecated`, `renamed_from`.

**`FactDef`** (delta): `description`, `examples`, `aliases`, `roles`,
`attributes`, `time`, `required`, `version_key` (roles, attributes and
`issuer`), `extract`, `agent_visible`, `exact_mappings`, `deprecated`,
`renamed_from`.

**`Retrieval`:** `hub_penalty` (types), `max_hops` (int ≥ 1),
`context_relations` (relation names). All optional. Query-time.

**`GlossaryEntry`:** `name` (text, required), `type` (an entity type,
required), `aliases` (texts), `note` (text).

**`CompetencyQuestion`:** `id`, `text` (both required), `needs` (a
non-empty list of type or relation names).

## 3. Merged stack

`PackStack` is what `load_pack` returns: frozen dataclasses with
`slots=True`, mappings wrapped in `MappingProxyType`, sequences as
tuples. It holds resolved values: every default of §2 is filled in, and
`is_a` parents' roles, attributes and `time` are copied into each child.

```
PackStack
├── name, version          the top pack's
├── mode                   Mode.STRICT | Mode.DISCOVERY: the top pack's, else the nearest ancestor's
├── stamp                  Stamp(name, version, content_hash)
├── index_hash             "sha256:…" (§5)
├── glossary_hash          "sha256:…" (§5)
├── packs                  tuple[PackInfo, ...] in linear order, core first
├── entities               Mapping[str, EntityType]
├── relations              Mapping[str, RelationType]
├── events                 Mapping[str, EventType]
├── facts                  Mapping[str, FactType]
├── enums                  Mapping[str, tuple[str, ...]]
├── not_entities           tuple[str, ...]
├── retrieval              Retrieval
├── glossary               tuple[GlossaryEntry, ...]
├── competency_questions   tuple[CompetencyQuestion, ...]
├── origins                Mapping[str, str]: element path → the pack that added it
└── warnings               tuple[PackProblem, ...]
```

- `PackInfo(name, version, source, file_hash)`: `source` is `"shipped"`
  or the absolute path of the file.
- `EntityType(name, description, examples, aliases, attributes, scope,
  identity, vetoes, names, corroborate, version_start, document_link,
  required, extract, agent_visible, exact_mappings, deprecated,
  renamed_from)`.
  - `scope`: `Scope(role, to, inherit, when)` or none.
  - `identity`: `tuple[Key, ...]` in the order resolution tries them;
    `Key(attributes: tuple[str, ...], during: tuple[str, str] | None)`.
  - `names`: `NameRule.KEY | EVIDENCE | VERSIONED | NONE`.
- `Attribute(name, range, multivalued, unit, description, compare,
  unique)`. A type's `required` tuple holds both its `required` list and
  its attributes marked `required: true`.
- `RelationType(name, description, from_types, to_types, where, time,
  attributes, value, cardinality, required, extract, exact_mappings,
  deprecated, renamed_from)`.
- `EventType(name, description, examples, aliases, is_a, roles,
  attributes, time, identity, required, extract, agent_visible, …)`.
  `roles` is `Mapping[str, tuple[str, ...]]`.
- `FactType(name, description, examples, aliases, roles, attributes,
  time, required, version_key, extract, agent_visible, …)`.
- Type maps are sorted by name, as are attribute and role maps.

**Order.** A list whose order means nothing is sorted, so reordering it
changes no hash and no compiled schema. A list whose order matters keeps
it:

| Sorted | Kept in order |
|---|---|
| `from`, `to`, role types, scope `to`, `where` values, enum values, `vetoes`, `required`, `corroborate`, `document_link`, `not_entities`, `hub_penalty`, `context_relations`, a fact's `version_key`, an event identity entry's names, `exact_mappings`, `cardinality` | `identity` keys (tried in order), a key's attributes (as written, which case elements repeat), `version_start` (tried in order), `examples` and `aliases` (prompt order), competency questions (linear pack order, then file order), glossary entries (file order) |

**Element paths** in `origins` and in problems:
`entities.Person`, `entities.Person.attributes.employee_id`,
`entities.Person.identity[scope+employee_id]`,
`entities.Person.vetoes[employee_id]`,
`entities.Organization.scope.inherit`,
`entities.Organization.scope.when.category[branch]`,
`relations.OWNER_OF.to[System]`, `enums.OrgCategory[branch]`.

## 4. Stacking

Research R3 has the rules and their reasons; §1 has the rule ids. In
short:
1. Each reference resolves to one file. The linear order is
   depth-first over `extends`, post-order, each pack once.
2. Files are applied in that order. A definition new to the stack is
   taken whole and must have a `description` (entity, event and fact
   types). A definition already in the stack is a delta: each field it
   states must either add (the "Allowed change" table of R3) or equal
   the stack's value.
3. Defaults are filled in, `is_a` is resolved, sets are sorted, and §1's
   check phase runs.

Example. `enterprise-docs` over `core`, for `Person`:

| Field | `core` | `enterprise-docs` states | Merged |
|---|---|---|---|
| `scope` | `{role: employer, to: [Organization], inherit: none}` | `{inherit: document}` | `{role: employer, to: [Organization], inherit: document}` |
| `identity` | `[[email]]` | `[[scope, employee_id]]` | `[[scope, employee_id], [email]]` |
| `vetoes` | none | `[employee_id]` | `[employee_id]` |
| `attributes` | `email` | `employee_id` | `email`, `employee_id` |
| `names`, `corroborate` | `evidence`, `[MEMBER_OF, HOLDS_POSITION]` | not stated | unchanged |

## 5. Hashes and the stamp

All four are `"sha256:" + hex` of the UTF-8 bytes of canonical JSON:
`{"format": 1, "kind": <name>, "content": <value>}`, sorted keys, compact
separators, `ensure_ascii=False`, `allow_nan=False`, strings in NFC
(M0's `_digest`, with the stage replaced by the hash kind).

| Hash | `kind` | `content` |
|---|---|---|
| content hash | `pack-content` | the merged stack of §3 without `name`, `version`, `packs`, `origins`, `warnings` and the hashes themselves |
| index hash | `pack-index` | the content above without `retrieval` and `glossary` |
| glossary hash | `pack-glossary` | the merged glossary; `[]` when there is none |
| file hash | `pack-file` | one file's validated model, without unset fields |

Enum members serialize as their values. A default written out equals the
default left out, in every hash except the file hash.

**Pins.** `tests/unit/packs/test_shipped.py` holds
`{("core", 1): "sha256:…", ("enterprise-docs", 1): "sha256:…"}`. A shipped
file whose hash differs from its pin fails, naming the pack and saying to
bump `version` and add a pin. Pins are never edited, only added.

## 6. Compiled schema and coverage

**`CompiledSchema`**, returned by `compile_schema`:

| Field | Type | Meaning |
|---|---|---|
| `schema` | dict, a fresh deep copy on each read | the JSON Schema of research R6, in plain dicts and lists: M0's `check_schema` runs jsonschema's meta-schema check, which accepts only `dict` (a `MappingProxyType` fails it, checked 2026-10-12). The copy keeps the compiled object unchanged |
| `types` | `tuple[str, ...]` | the types it covers, sorted |
| `property_count` | int | the sum of every `properties` map's size, as M0's `check_schema` counts |
| `to_json()` | `str` | sorted keys, compact separators, `ensure_ascii=False` |

Excerpt for `core` (whitespace added here only):

```json
{"type": "object", "additionalProperties": false,
 "required": ["entities", "events", "facts", "relations"],
 "properties": {
  "entities": {"type": "array", "items": {"type": "object", "additionalProperties": false,
    "required": ["attributes", "former_names", "id", "is_name", "name", "ref", "scope", "surface", "translation", "type"],
    "properties": {
      "type": {"type": "string", "enum": ["Concept", "Metric", "Organization", "Person", "Place", "Product", "Work"]},
      "attributes": {"type": "array", "items": {"type": "object", "additionalProperties": false,
        "required": ["name", "quote", "value"],
        "properties": {"name": {"type": "string", "enum": ["category", "code", "email", "established_on", "issued_on", "kind", "registration_id", "title", "unit"]},
                       "value": {"type": "string"}, "quote": {"type": "string"}}}},
      "…": "id, surface, is_name, name, translation, ref, scope, former_names"}}},
  "relations": "…", "events": "…", "facts": "… Definition and ReportedFigure; Statement is extract: false"}}
```

**`CoverageReport`**, returned by `check_coverage`:
- `questions`: `tuple[QuestionCoverage, ...]` in stack order;
- `QuestionCoverage(id, text, pack, missing, not_extracted)`, where
  `missing` and `not_extracted` are sorted tuples of names and `passed`
  is true when both are empty;
- `passed`: true when every question passes.

## 7. Profile field (delta to M0 data model §2)

| Path | Type | Default | Phase |
|---|---|---|---|
| `pack` | pack reference | `core` | operational |

- A value ending in `.yaml` or `.yml` is a path; anything else must match
  the pack name pattern of §2. The profile checks only this syntax.
- `load_profile` makes a relative path absolute against the profile
  file's directory. The other two loaders keep it as written.
- Operational, so it enters no stage hash itself. The pack's content
  enters through `stage_hashes(profile, pack_hash=…)` (M0 data model §8):
  `fields["pack"] = pack_hash` in the `extract` and `resolve` stages.

## 8. Identity cases

A case file is YAML, validated by `tenetrag/packs/cases.py` with the
same rules as a pack file (safe loading, duplicate keys, NFC,
`extra="forbid"`).

```
CaseFile
├── pack        reference: a shipped name, or a path relative to the case file
├── entities    map of entity id → CaseEntity
└── cases       list of Case
```

**`CaseEntity`:**

| Field | Type | Notes |
|---|---|---|
| `type` | entity type | must exist in the stack |
| `name` | text | required |
| `aliases` | texts | |
| `scope` | entity id | the immediate scope; its own scope gives the path |
| `attributes` | map of attribute → `{value, quote}` | both texts, non-empty |
| `relations` | list of `{type, to, attributes, valid_from, valid_to}` | `to` is an entity id; dates optional |
| `former_names` | list of `{name, quote}` | |

**`Case`:**

| Field | Type | Notes |
|---|---|---|
| `id` | `^[A-Z]+-[0-9]+$` | unique across all case files |
| `origin` | `design` \| `added` | `design` for the 60 of ADR 0016 |
| `expect` | `merge` \| `apart` | |
| `title` | text | the original Vietnamese title for design cases |
| `existing` | entity ids | the graph before the mention |
| `mention` | `Mention` | |
| `outcome` | `Outcome` | |
| `depends_on` | elements | at least one |
| `blocked_by` | attribute | required when a veto keeps the pair apart |

**`Mention`:** the `CaseEntity` fields without `aliases`, plus
`scope_source` (`text` \| `document`; `document` means the scope was
inherited from the document), `translation` (text), and `document`:
`{issuer: entity id or none, date: ISO date, language: vi | en}`.

**`Outcome`**, by `kind`:

| Kind | Fields | Allowed with |
|---|---|---|
| `merge` | `into`: an existing id | `expect: merge` |
| `confirm` | `candidates`: existing ids; `right`: one of them | `expect: merge` |
| `new` | none | `expect: apart` |
| `same_as` | `links`: existing ids | `expect: apart` |

**Elements** in `depends_on`: `scope`, `key:<a>+<b>` (the key's
attributes in its written order, `scope` included), `veto:<a>`,
`names:<rule>`, `unique:<a>` (an attribute's non-default `unique`) and
`corroborate:<RELATION>`. Each must exist on the mention's type in the
case's stack.

**Problems** from `check_cases`, each a `PackProblem` whose `file` is the
case file and whose `path` is `cases[<id>]...`:

| Rule id | When |
|---|---|
| `case.duplicate-id` | an id appears twice across the files checked together |
| `case.unknown-entity` | an id in `existing`, `scope`, `relations`, `document.issuer` or the outcome is not in `entities` |
| `case.unknown-type` / `case.unknown-attribute` / `case.unknown-relation` | a name the case's stack lacks for that type |
| `case.unknown-element` | a `depends_on` element the mention type lacks |
| `case.outcome` | the outcome kind does not fit `expect`, or names an id outside `existing` or `candidates` |
| `case.blocked-by` | `blocked_by` is set but `veto:<it>` is not in `depends_on`, or a `new` outcome depends on a veto and has no `blocked_by` |
| `case.coverage-type` | a type the top pack defines or changes identity for lacks a merge or an apart case (FR-031) |
| `case.coverage-element` | a key or veto the top pack declares is named by no case (FR-031) |

The two coverage rules run per shipped pack: the identity elements that
`origins` attributes to the stack's top pack must each be covered.

## 9. Corpus

**Fact table** (input, edited by hand), under
`tests/fixtures/corpus/facts/`:

| File | Holds |
|---|---|
| `world.yaml` | entities by world id: type, name, aliases, scope, attributes. Fictional only |
| `documents/<id>.yaml` | one document: metadata, blocks and items |
| `graph.yaml` | deletion scenarios and `TEXT_IN` links (research R12) |
| `golden.yaml` | hand-written golden questions |

**Document file:**

| Field | Type | Notes |
|---|---|---|
| `id` | `D<n>` | D1 to D5 are the running example |
| `language` | `vi` \| `en` \| `mixed` | |
| `issuer` | world id | the letterhead |
| `title` | text | |
| `format` | `docx` `pdf` `pptx` `xlsx` `md` | a label until feature 004 renders other formats |
| `dates` | map of name → ISO date | only dates the text states |
| `blocks` | list of `{heading, level}`, `{paragraph}`, `{list: [...]}` or `{table: {header, rows}}` | the text, written in the document's language; `level` is 1 to 3, default 1 |
| `items` | list of expected items | below |

**Expected item:** `id` (`<doc>.<n>`), `kind` (`entity`, `relation`,
`event`, `fact`), `type`, and by kind:
- entity: `world` (the world id it denotes), `surface`, `is_name`,
  `attributes` (`{value, quote}`), `former_names`;
- relation: `from`, `to`, `attributes`;
- event and fact: `roles` (role → one ref or a list), `attributes`;
- relations, events and facts: `quote`, and `valid_from`, `valid_to`
  when the text states them.

A ref is an item id of the same document, so a fact about an entity
needs that entity's own item. Items link across documents only through
their entities' `world` ids. Every attribute is `{value, quote}`, as in
the compiled schema.

**Generated files** (output, committed), under
`tests/fixtures/corpus/generated/`:

| File | Holds |
|---|---|
| `docs/<id>.md` | the rendered document: NFC, LF, Vietnamese formats in the text |
| `documents.jsonl` | one line per document: metadata, `path`, and its items |
| `graph.json` | `entities` (world id → item ids), `versions` (group → members with `status` and `closed_at`), `supersedes`, `text_in`, `deletions` (document → changed statuses) |
| `golden.jsonl` | one question per line (below) |

**Golden question** (the benchmark's fields, SDK brief, Benchmark):

| Field | Type | Notes |
|---|---|---|
| `question` | text | in the language of `tags.lang` |
| `expected_answer` | text | from the fact table, figures verbatim |
| `expected_sources` | list of document ids | sorted |
| `tags` | map of string → string | `id`, `qtype`, `lang`, `cq`, `as_of`, `origin` |

`qtype` is one of `single_fact`, `entity_all`, `meeting_decision`,
`definition`, `historical_figure`, `as_of`, `conflicting_versions`,
`cross_lingual`. `cq` lists question ids separated by commas, `as_of`
is an ISO date or `""`, and `origin` is `generated` or `hand_written`.
Q-a, Q-b and Q-c keep those ids.

**Running example, as the corpus states it:**

| Item | Version group | Status | `closed_at` |
|---|---|---|---|
| r1, D1: 2.000.000 VND/ngày, from 2025-02-01 | Requirement, issuer Alpha, metric phụ cấp lưu trú | `superseded` | 2026-01-15 |
| r2, D2: 2.500.000 VND/ngày, from 2026-01-15 | the same group | `current` | |
| D5's limit: 800.000 VND/ngày, from 2026-03-15 | Requirement, issuer Beta, the same metric name | `current` | |
| after deleting D2: r1 | | `current` | none |
