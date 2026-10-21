# Normalize text by the languages the profile names

**Status:** accepted; amends [0008](0008-build-databricks-and-open-branches-in-parallel.md)
**Date:** 2026-10-21
**Deciders:** Liam Lee (review of feature 003 phase 2, 2026-10-21)

## Context
Engine brief §7 and ADR 0008 §4 define one normalization for all text:
NFC, the Vietnamese tone-mark table (`hoà` → `hòa`), casefold and
whitespace collapse. Phase 2 of feature 003 built it that way in
`tenetrag.engine.text` (commit 1bdd3ed). TenetRAG is open source, and
most corpora it will index are not Vietnamese. A rule written for one
language should not run on every corpus by default. Its code should sit
apart too, so that a second language adds a module instead of growing a
shared one.

Matching compares normalized forms. A name in the store and a query
string meet only when both went through the same rules.

## Decision
1. **Shared steps for every text.** `norm(text, *, languages=())` runs
   NFC, casefold, NFC again and whitespace collapse on every text. These
   lose no meaning in any language.
2. **One module per language with extra rules.**
   `tenetrag.engine.text.vi` holds the tone-mark table, and
   `LANGUAGE_RULES` maps a language code to its rule. A language with no
   entry adds nothing. Rules run after casefolding, in the order of their
   codes.
3. **The profile names the corpus's languages.** `text_languages` is a
   sorted set of ISO 639 codes, empty by default. The engine passes it to
   `norm` at index time and at query time alike, for every text, whatever
   that text's own language tag. A Vietnamese corpus sets
   `text_languages: [vi]`.
4. **The field is index-time, in the chunk stage.** Changing it changes
   every `_norm` field, so it enters the hash of the chunk stage, the
   first stage that writes one ([ADR 0005](0005-index-time-vs-query-time-parameters.md)).
   Feature 004 recomputes every `_norm` field of a document whose chunk
   stage hash changed. The extraction cache, keyed on the extraction
   stage hash, still serves the model's output.

## Alternatives considered
- **Keep the tone-mark table on for every text.** Rejected: an
  open-source SDK would run a Vietnamese rule by default, and one shared
  module would grow with each language.
- **Pick the rules by each text's language tag**, such as a chunk's
  `vi`, `en` or `mixed`, or an alias's language. Rejected:
  - a query has no reliable tag;
  - a `mixed` chunk has no clear rule;
  - a Vietnamese name quoted in an English document would skip the rule
    and miss the alias from a Vietnamese document, so one person would
    get two `name_norm` forms.
- **Refuse codes that have no rules.** Rejected: the profile lists the
  corpus's languages, and `en` is a fair answer even with no extra rule
  today. The cost is that a mistyped code such as `vn` adds nothing; the
  code pattern catches only malformed codes.

## Consequences
**Better:**
- A corpus in any language gets the shared steps and nothing written for
  another language.
- A new language rule is one module and one registry entry, with its own
  tests.
- Index and query text always meet under the same rules.

**Worse:**
- A Vietnamese deployment must set `text_languages: [vi]`. Without it,
  `hoà` and `hòa` stay apart.
- Each enabled rule runs on all text, so a rule must be safe on the
  other languages a profile lists. The tone-mark rule touches only the
  fifteen Vietnamese vowel pairs, and only at the end of a syllable.
- The new field changed the chunk stage hash of every profile. No index
  exists before feature 004, so nothing needs re-indexing.

**Must now be true:**
- Engine brief §2.1, §7 and §9, the platform brief, and feature 003's
  FR-047, `contracts/text.md`, `contracts/config.md`, data-model §11 and
  research R18 describe rules named by the profile.
- The contract suite's fixtures normalize with `languages=("vi",)`, the
  languages of the synthetic corpus.
- ADR 0008's status notes this amendment.

**Left open for feature 004:** other defaults written for Vietnamese
might follow the same rule. These are the Vietnamese and English
`resolution.legal_forms`, the Vietnamese `resolution.self_scoped_codes`,
and the chunk language tag's heuristic on Vietnamese letters (engine
brief §2.1, §9). 004's plan settles them.

## Revisit if
- A language needs a rule that is unsafe on text of other languages.
  Rules would then have to follow each text's language, with the query
  side solved first.
- Users need rules of their own without a release. `LANGUAGE_RULES`
  would then take entries from outside the SDK.
