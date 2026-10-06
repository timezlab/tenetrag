# Enterprise documents: meetings, obligations, definitions and versions in papers

> **Snapshot, 2026-10-04 — not maintained.** Academic lane; partial coverage, mostly abstract-level. The maintained,
> re-verified summary is in [domain-schemas.md](../reference/domain-schemas.md); where they differ, the maintained doc
> wins. Local paths were removed before publishing.
>
> **Errata and later resolutions:**
> - AMI license confirmed as CC BY 4.0. Decision-related dialogue acts are defined through
>   the extractive summary that supports the abstractive decisions summary.
> - VersionRAG (90 % vs 58 % naive RAG and 64 % GraphRAG, 100 questions) confirmed; preprint.
> - EnterpriseRAG-Bench categories confirmed; its dataset is MIT-licensed.
> - ComplianceNLP's four deontic classes confirmed.

## r4: Enterprise-document extraction literature, for enterprise-docs (2026-10-04)

Labels: [primary] = read on the owning arXiv/MSR page this session (abstract or HTML, not always the full body); [secondary] = search snippet; [inferred] = my reasoning.
Coverage is partial: about 21 tool calls. Several PDFs did not render (see Gaps). Few numbers are verified.

### 1. Summary
- Meetings: AMI has no explicit action-item layer. Action items are derived from dialogue acts linked to the abstractive "actions" summary (101 meetings, 381 items). The decision layer marks decision-related dialogue acts and links them to the decision summary. [secondary] https://arxiv.org/pdf/2303.16763 ; https://groups.inf.ed.ac.uk/ami/corpus/annotation.shtml
- No public meeting corpus I found annotates owner plus due date plus status as fields. This is a real gap, and a graph schema can add these fields without literature precedent. [inferred]
- Policies: LLM pipelines classify sentences as obligation, permission or prohibition (ComplianceNLP adds RECOMMENDATION). This matches your Requirement modality (must/should/may/must_not). [secondary] https://arxiv.org/pdf/2604.23585
- Process extraction: the PET dataset has 7 mention types (activity, actor, data object, gateways, etc.) and 6 relation types. This argues for a Step/ordering notion inside Procedure, not a separate Role type. [secondary] https://arxiv.org/pdf/2407.18540
- Definitions: DEFT (SemEval-2020 Task 6) splits the task into sentence classification, token tagging of concepts, and relations between them. A definition is therefore a span-grounded relation between a term and a gloss. [secondary] https://arxiv.org/abs/2008.13694
- Enterprise KGs: Enterprise Alexandria (AKBC 2021) builds typed entities with organization-specific custom types, "eyes-off" and with online curation. [primary] https://www.microsoft.com/en-us/research/?p=773734
- Enterprise RAG benchmark: EnterpriseRAG-Bench (2026) has 500 questions in 10 categories over 500k synthetic documents. It includes "Conflicting Info" (20) and "Info Not Found" (20), and there is no explicit "which version on date D" category. [primary] https://arxiv.org/html/2605.05253
- Versions: VersionRAG reports 90% accuracy versus 58% naive RAG and 64% GraphRAG on 100 questions over 34 versioned documents (single-paper, small). Implicit-change questions: 60% versus 0-10%. [primary, abstract] https://arxiv.org/abs/2510.08109
- Recommendation: keep Decision as an Event, add a `Definition` claim with versions, and add `Metric` as an entity. Do not add Term, Step, Role, Goal or Risk as types. Details in section 4.

### 2. Sources table
| Paper | Venue | Peer review | Types / content | License |
|---|---|---|---|---|
| AMI annotation (Carletta et al.; Fernandez et al. 2008 decisions) | AMI portal; Interspeech 2008 | yes (Interspeech) | dialogue acts, decision DAs, abstractive decisions/actions/problems | not checked |
| Action-item detection w/ regularized context (arXiv 2303.16763) | arXiv (venue not checked) | preprint as seen | AMI-derived (101 mtgs, 381 items); first Chinese corpus with manual action-item labels | not checked |
| QMSum (2104.05938) | NAACL 2021 | yes | 232 meetings, 1,808 query-summary pairs; query schema (overall content, opinions, reasons) | not checked |
| GADR (2608.17694) | arXiv 2026 | preprint | Nygard ADR drafts from transcripts; 5 transcripts, 4 expert architects | no public set |
| ComplianceNLP (2604.23585) | arXiv 2026 | preprint | OBLIGATION/PERMISSION/PROHIBITION/RECOMMENDATION | n/a |
| PolicyKG (2608.09028) | arXiv 2026 | preprint | deontic O/P/F to SHACL; PDF did not render | n/a |
| PET + universal prompting (2407.18540) | arXiv | preprint | 45 docs, 7 mention + 6 relation types | not checked |
| DEFT / SemEval-2020 T6 (2008.13694) | SemEval 2020 | yes | def-sentence, token tags, relations; textbooks | not checked |
| SDU@AAAI-21 (Primer AI 2012.08013) | AAAI-21 workshop | workshop | acronym ID and disambiguation; top AD F1 ~0.94 (snippet) | not checked |
| Enterprise Alexandria | AKBC 2021 | yes | typed entities, custom types | n/a |
| EnterpriseRAG-Bench (2605.05253) | arXiv 2026 | preprint | 10 categories, 9 sources | "arXiv perpetual non-exclusive" shown on page; dataset license not found |
| ConcurrentQA (2203.11027) | ACL 2022 (venue not checked) | likely | 18,439 Q; 80% bridge, 12% attribute, 8% comparison; emails + Wikipedia | not checked |
| TechQA (1911.02984) | arXiv/IBM | preprint | 1,400 Q; info, how-to, problem-cause-solution | not checked |
| WixQA (2505.08643) | arXiv 2025 | preprint | enterprise support RAG | not checked |
| VersionRAG (2510.08109) | arXiv 2025 | preprint | version graph; VersionQA 100 Q/34 docs | not checked |
| TimelyRAG (2609.11572) | arXiv 2026 | preprint | TimelyQABench: clauses revised in eligibility, scope, effective period, exceptions, required actions | not checked |

### 3. Findings per question

**Q1 Meetings.**
- AMI decision annotation: annotators mark decision-related dialogue acts and link them to a decision summary. [secondary] https://groups.inf.ed.ac.uk/ami/corpus/annotation.shtml ; guidelines https://groups.inf.ed.ac.uk/ami/corpus/Guidelines/decision_annotation-boundary-v1.4.pdf (not read).
- AMI action items: derived from actions-summary links to dialogue acts, not a direct annotation. Fields such as owner and due date are not annotated. [secondary] https://arxiv.org/pdf/2303.16763
- QMSum uses a query schema (overall content, speakers' opinions, reasons for proposals). The "reasons" facet supports a rationale field on Decision. [secondary] https://arxiv.org/pdf/2104.05938
- ICSI, MeetingBank and ELITR schemas: not verified, only mentioned in snippets. See Gaps.
- LLM numbers on decisions: GADR is a qualitative feasibility study ("captures most expert-identified decisions"). It found that RAG enrichment added transcript-unfaithful content. No F1 was found. [primary, abstract] https://arxiv.org/abs/2608.17694 `single-paper`
- No LLM F1 numbers for owner, due date or status extraction were found. Treat any claimed accuracy as unknown.

**Q2 Policies, requirements, procedures.**
- Deontic modalities: ComplianceNLP uses four sentence-level classes, which includes a weaker "recommendation" (= should). [secondary] https://arxiv.org/pdf/2604.23585
- PolicyKG: described in the search snippet as O/P/F deontic operators translated to SHACL. My fetch claimed Agent/Action/Condition/Exception/Deadline roles. I could not read the PDF, so I discard that role list as unverified. [secondary] https://arxiv.org/pdf/2608.09028
- EARS: ubiquitous / event-driven (WHEN) / state-driven (WHILE) / optional (WHERE) / complex patterns. This gives condition-type distinctions. LLM-rewritten requirements were rated similar to human rewrites, especially for short ones. [secondary] https://arxiv.org/pdf/2310.13976
- BPMN: PET has activity, actor, data-object and gateway mentions plus flow relations. Parallel gateways are often missed. [secondary] https://arxiv.org/pdf/2407.18540
- Role vocabulary across these: agent/actor, action, condition, exception, deadline. This is [inferred] from the generic literature, not verified per paper.

**Q3 Definitions.**
- DEFT: sentence classification, token tagging, relation classification. [secondary] https://arxiv.org/abs/2008.13694
- SDU@AAAI-21: acronym identification and disambiguation. [secondary] https://arxiv.org/pdf/2012.08013
- Glossary induction and KPI-formula extraction from documents: no peer-reviewed work found. The hits were metrics-layer vendor pages and an ontology-based KPI explorer, where formulas live in the ontology. [secondary] https://www.springerprofessional.de/en/an-ontology-based-data-exploration-tool-for-key-performance-indi/4393686
- Representation [inferred]: a definition with formula, version, time and source is a claim (versioned, multi-source), not an entity attribute. An attribute overwrites history, and a separate Term node adds an entity that fails the "fine distinctions are enum values" rule. The `Metric` entity is the defined thing. The `Definition` claim links Metric (or Concept) to the formula text verbatim.

**Q4 Enterprise KGs.**
- Enterprise Alexandria: typed entities from private documents, with custom types per organization, online curation, and eyes-off privacy. [primary] https://www.microsoft.com/en-us/research/?p=773734
- Alexandria (Winn 2019) and Viva Topics: topics with descriptions, documents, and people. The type list and failures were not found. [secondary] https://www.microsoft.com/en-us/research/?p=741421
- IBM, SAP and LinkedIn: not searched (budget).
- "What failed" is not answered by sources read.

**Q5 Benchmarks.**
- EnterpriseRAG-Bench categories: Basic 175, Semantic 125, Intra-Doc 40, Project 40, Constrained 30, Conflicting Info 20, Completeness 20, Misc 20, High Level 10, Info Not Found 20. BM25 scored 90% on Conflicting Info, 40% on Completeness, 44.8% on Semantic (as reported by the paper's Table 7 via the page extract). [primary] https://arxiv.org/html/2605.05253
- ConcurrentQA: bridge, attribute, comparison. TechQA: info, how-to, problem-cause-solution. [secondary] https://arxiv.org/pdf/2203.11027 ; https://arxiv.org/pdf/1911.02984
- Not found as benchmark categories: "what was decided about X", "who owns X", "what does term T mean". [inferred] These are CQs you should author rather than expect to borrow.
- WorkBench, Enterprise RAG Challenge, MultiHop-RAG, DocBench: not read.

**Q6 Versions and supersession.**
- VersionRAG models version sequences and changes in a graph, with intent routing. VersionQA is small (100 Q). [primary, abstract] https://arxiv.org/abs/2510.08109 `single-paper`
- TimelyRAG and TimelyQABench: clauses revised in eligibility, scope, effective period, exceptions, required actions. These suggest what a Policy change record should capture. [secondary] https://arxiv.org/pdf/2609.11572
- "Version conflation" is the named failure mode: standard RAG retrieves several versions at once. [secondary, same source]
- EnterpriseRAG-Bench evaluates conflict handling through document validity judgments, not a version model. [primary]

### 4. Proposed enterprise-docs changes
1. Keep `Decision` an Event (made_in Meeting). Add roles `rationale` (text) and `alternatives` (optional), and keep `status` an enum. Reason: QMSum "reasons" facet; AMI links decisions to meeting segments; GADR ADRs need context/alternatives. Source: QMSum, GADR. [inferred mapping]
2. Add `Definition` claim: roles `defines` (Metric or Concept), `text` (verbatim), `formula` (verbatim string), `scope` (optional). Time and source come from the engine fields. Return all versions ordered by time. Reason: DEFT treats definition as term-gloss relation, no source treats it as an attribute. Source: DEFT. [inferred]
3. Add `Metric` entity (name, unit as attribute, aliases). Reason: it is the thing defined, and acronyms are aliases. Avoid a separate `Term`; use Concept plus aliases. Source: SDU acronym tasks. [inferred]
4. `ActionItem`: add `description` and `status` enum (open/done/dropped); keep owner, due_date. No annotation scheme supports these fields in public meeting corpora, so they are an engineering choice. [inferred]
5. `Requirement`: keep must/should/may/must_not. Add optional `condition` and `exception` text attributes, and `deadline` as a date attribute. Source: ComplianceNLP (4 classes), EARS condition patterns. Add `enforcement_level` only if needed later.
6. `SUPERSEDES`: add time kind point (effective date), and allow Policy to Policy, Procedure to Procedure, Definition to Definition. Reason: version conflation failure; TimelyQABench revision facets. Source: VersionRAG, TimelyRAG.
7. Do not add `Step`, `Role`, `Goal`, `Risk`, `Issue`, `Campaign` as types now. `Step` is an ordered attribute list on Procedure unless step-level queries are a CQ. Role overlaps HOLDS_POSITION. Campaign is a Project with a `ProjectKind` enum. Risk and Issue: add as ClaimKind enum values only if CQs need them (no literature support found either way). [inferred]
8. Add `Meeting` roles: `chair`, `minute_taker` as enum values on attendee role, consistent with minuting corpora (ELITR not verified).

### 5. Competency questions
1. What was decided about X, in which meeting, and why? (Decision rationale; QMSum "reasons")
2. Which action items are open, who owns each, and what is the due date? (ActionItem)
3. Who owns Policy/Procedure/System X now, and who owned it on date D? (OWNER_OF)
4. Which version of Policy X applied on date D? (SUPERSEDES; TimelyQABench-style)
5. What changed between version N and N+1 of Policy X? (VersionRAG implicit change)
6. What does term or acronym T mean, and has its definition changed? (Definition; SDU, DEFT)
7. How is metric M calculated, and which sources give conflicting formulas? (Definition; Conflicting Info category)
8. What must / must not be done under Policy X, under what condition, with what exception? (Requirement)
9. Which Procedure implements Policy X, and which System does it use? (IMPLEMENTS, USES)
10. Which decisions are superseded by later decisions? (Decision, SUPERSEDES)
11. Which Requirements apply to Project/System Y? (APPLIES_TO)
12. Is there any document stating Z? Answer "not found" otherwise. (Info Not Found category)

### 6. Gaps
- Not verified: ICSI, MeetingBank, ELITR schemas; ELITR/MeetingBank sizes; AMI decision guideline body.
- No LLM extraction numbers for owner, due date, status; none for decision extraction.
- PolicyKG, 2303.16763 PDFs did not render; PolicyKG role list discarded.
- Not covered: IBM/SAP/LinkedIn enterprise KGs, Alexandria failures, WorkBench, Enterprise RAG Challenge, MultiHop-RAG, DocBench, glossary induction, KPI extraction from text.
- Dataset licenses mostly unchecked.
- Many 2026 arXiv items are preprints seen only via abstract or snippet.
