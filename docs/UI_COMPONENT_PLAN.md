# UI Component Plan & Handoff — Explore / Shortlist & Compare / Ask

* **Author:** Adarsh Patel
* **Date:** 2026-11-11
* **Branch:** `ui-revamp` (public repo `gujrera-intelligence`; private `gujrera-pipeline` untouched on `main`)
* **Status:** Dashboard fixes complete and verified; design concept reviewed by six Goldfish lenses 2026-11-11 (5 × SHIP WITH CHANGES, 1 × NOT READY → resolutions adopted); frontend recommendation below endorsed by the review with one added refactor step.

---

## 1. Fixes Completed (verified 2026-11-09/11)

All fixes are in the current stack, no new dependencies. `real_estate_intelligence/tests/test_ui_server.py`: **18/18 pass** (16 pre-existing + 2 new regression tests).

| # | Issue | Fix | Verification |
|---|---|---|---|
| 1 | `/api/verify_claim` non-numeric input killed the connection (HTTP 000); client button failed silently | Server: `try/except` → 400. Client: input validation + error card | `curl` probe → HTTP 400; regression test `test_verify_claim_invalid_numeric_returns_400` |
| 2 | Every project listed itself as a sister scheme (all 9 `previous_projects` rows self-link) | `/api/project/{pid}` SQL excludes `linked_project_id = pid` | API returns real sisters; regression test `test_project_payload_excludes_self_sister_scheme`; UI screenshot |
| 3 | Copilot printed "Cash Runway Assessment: None" | Narrative presence guard | Escrow query reply no longer contains the None line |
| 4 | Page-level horizontal overflow on mobile (document 609 px at 360 px viewport: header select + unwrappable mono registration number) | Responsive stacked header, full-width constrained select, `break-all` on registration number | Measured `scrollWidth 360 == clientWidth 360`, forced-scroll `scrollX 0`; mobile screenshot |
| 5 | KPI "RERA Deadline" wrapped mid-value | `whitespace-nowrap tabular-nums` on KPI values | Desktop screenshot |
| 6 | Enter did nothing in Document Search | Enter handler on input | Enter produced 6 result cards (0 before) |
| 7 | Copilot drawer: no Esc; launcher overlapped drawer | Esc closes; launcher hidden while open; restored on close | Both states asserted live in browser |
| 8 | No loading/empty/error states on any fetch; stale panels persisted across project switch | `fetchJSON` helper, global error banner (dismissible), per-panel loading/error/empty states, stale-panel clearing on project change | Forced `loadProject(99999)` → banner "HTTP 404" + "Failed to load project"; healthy reload clean |
| 9 | Hardcoded default project `16562` | First-project fallback from `/api/projects` | Loads Skydeck Serene (13560) |
| 10 | Tabs lacked ARIA semantics, arrow-key nav; active tab could sit outside the scrolled strip | `tablist/tab/tabpanel` + `aria-selected`, ←/→ navigation, auto-scroll to active tab, focus-visible outline | ARIA states flip; strip `scrollLeft 112` on switching to last tab; live click timeouts on off-screen tabs eliminated |
| 11 | Unescaped filing data injected into `innerHTML` | `esc()` / `escSnippet()` (preserving FTS `<b>` highlights) on all DB-derived interpolations | All panels render; escaping helper verified in emitted HTML |
| 12 | Hardcoded "Verified" badge; graph ignored current project; raw negative BM25 score shown | Honest "Registered" badge; graph auto-selects `project:<pid>` node; result-count label replaces BM25 number | Screenshot; `networkInstance.getSelectedNodes() == ["project:13560"]`; search card shows "Result 1 of 6" |
| 13 | Single-threaded server froze the whole dashboard during copilot LLM calls (documented EGM invariant) | `ThreadingHTTPServer` (`daemon_threads = True`); `ui/EGM.md` contract updated | 18/18 tests; live probe: `/api/projects` answered in 3.7 ms while a copilot call was in flight |

**Known limitation recorded, not fixed:** copilot replies (deterministic + LLM) render through a light markdown formatter without HTML escaping — first-party content today; flagged for the Ask-Across-Projects stage, where scope/expansion of the copilot forces a proper message renderer (see §5).

**Deferred to design review (not a fix):** CDN dependence of the "sovereign local-first" claim (Tailwind/Font Awesome/vis-network/Chart.js load from public CDNs; offline the UI is unstyled and chartless). Vendoring assets is a design decision, listed in the component mapping.

**Review-driven fix additions (identified 2026-11-11, queued before feature work):** eager model training in `setup_backends` (or init lock) — the MCP hedonic/survival models lazily train unguarded and would double-train under concurrent requests; copilot escape-then-markdown (`formatBotReply` currently interpolates unescaped markdown + FTS snippets + citations); graph self-link exclusion in `graph/network.py` (each project is duplicated as its own prior-project node) and `linked_gujrera_projects_count` self-link correction; guarded query-param parsing on `/api/search` + analytics routes (connection-drop instead of 400); `allow_nan=False` JSON serialization. The ThreadingHTTPServer safety rationale in `ui/EGM.md` also needs rewording (safety comes from the single serialized connection, not WAL; `KnowledgeGraph.__init__` performs a DDL write).

## 2. Proposed Workflows, 3. Acceptance Scenarios, 4. Data Coverage & Definitions

Canonical source: `docs/reviews/ui-discovery/concepts_brief.md` (reviewed 2026-11-11 — Overview, Analysis, Goals vs. Non-Goals, Alternatives Weighed, Key Decisions). The plan deliberately does not restate the concept: the earlier duplicates drifted from the brief on scenario 2 and the benchmark threshold. Release-1 scope highlights that differ from the pre-review draft, per the review: a new `/api/explore` aggregate endpoint (the old `/api/projects` payload cannot feed the filters); price columns restricted to BOOKED transactions (636 of 1,673 rows are UNBOOKED declared prices); filter rail collapsed to the discriminating filters; freshness as a date + days-ago column (no buckets); scenario 1 accepted on the Compare grid's revision column, not cross-project Ask.

## 5. Component Mapping (current vs Vue/shadcn-vue vs React/shadcn-ui)

Sources: official docs only — shadcn-vue.com (Data Table, Chart, Sheet), TanStack Table v9 docs via shadcn-vue guide, elements.ai-sdk.dev (AI Elements), ui.shadcn.com. The previously flagged agent skill was kept out of this workflow, as instructed.

| UI element | Current stack (owns ~1,500 lines of template JS) | Vue + Vite + shadcn-vue | React + Vite + shadcn/ui | Recommendation |
|---|---|---|---|---|
| Grouped filters | Hand-built chips/inputs; verified working | TanStack column filters + `Select`/`Popover`/`Checkbox` primitives; consumer writes all filter UI ("no opinionated data-table component" — guide only) | Same model (`@tanstack/react-table` + primitives) | **Current stack for release 1** — at 9 rows, client filtering is ~80 lines; shadcn filter UI is all consumer-written anyway |
| Sortable results table | Hand-built `<table>` + sort state | `Table` primitives + `@tanstack/vue-table` v9 (`tableFeatures()`, `FlexRender`, sorted/filtered/paginated row models) + recipes (`DataTableColumnHeader`, `DataTablePagination`) | Identical API surface on React | Vue/React buys a11y-verified table primitives + recipes; worth it only when the table grows past ~15 columns or statewide data lands |
| Charts (survival, SHAP waterfall, price trajectory) | Chart.js 4.4 UMD, working, owned | shadcn-vue charts = **Unovis** — Chart.js does not port into its chart layer; keep Chart.js standalone alongside or rewrite 3 charts | shadcn/ui charts = **Recharts** — same rewrite cost | Keep Chart.js regardless of framework choice; do not rewrite working analytics charts for a component catalog |
| Comparison table (side-by-side) | None yet | `Table` + `Card` composition; sticky first column is custom CSS | Same | Framework-neutral build; no differentiator |
| Evidence drawers / filing previews | Copilot drawer pattern (fixed div) | `Sheet` on Reka UI Dialog — focus trap, Escape, aria from the primitive | `Sheet`/`Drawer` on Radix Dialog — same | Both fine; current hand-built drawer now has Esc + labels but **no focus trap** — a real gap the primitives solve |
| Copilot messages & citations | Hand-built bubbles + citation chips + markdown-lite formatter (unescaped — known limitation) | **No official equivalent** | **AI Elements**: Conversation, Message, Sources, Inline Citation, Suggestion (chips), Prompt Input, Tool — *React-only*, and deprecated end of Nov 2026 as it folds into shadcn/ui | The only official catalog for this element is React-side. Material for the Ask-Across-Projects stage, not release 1; re-evaluate the fold-in result at that stage |
| Graph (vis-network) | vis-network UMD, working | No official wrapper; use vis-network standalone (framework-agnostic) | Community wrappers exist; official standalone works in both | Keep vis-network as-is in any stack |
| State preservation (filters/sort) | URL hash + sessionStorage (planned) | Same mechanism; `@vueuse` optional | Same | Framework-neutral |
| Data serving | `/api/*` JSON over stdlib server | Unchanged | Unchanged | No backend change in any option |

**Estimated integration effort (rough):** current-stack release 1 ≈ 600–900 new lines in the existing template (filters, table, chips, compare grid, scope selector). shadcn-vue route = scaffold app (½ day) + port 8 tabs of template JS into SFCs (3–5 days) + rebuild 3 charts in Unovis or re-wire Chart.js (1 day) + TanStack table wiring (1–2 days) — call it **6–9 days** before feature parity, then the same feature work. React route similar (**6–9 days**), with the AI Elements payoff arriving only at the Ask stage.

## 6. Frontend Recommendation (preliminary — pending Goldfish findings)

**Release 1 on the current Python-served UI.** At 9 projects, every planned element already works in the template; migration buys component polish, not capability, and costs 6–9 days of parity work before any new feature. The migration question is re-opened on two concrete triggers, not on preference: (a) statewide ingestion lands (real server-side filtering + pagination makes TanStack Table's row models worth their wiring), or (b) the Ask-Across-Projects stage begins (the only official copilot component catalog — AI Elements, folding into shadcn/ui — is React-side; if the fold-in lands well, that stage is the natural migration point). Code the team would own shrinks meaningfully in the long run only under trigger (b); under (a) it is roughly neutral.

## 7. EGM Review Status

- Concepts brief: `docs/reviews/ui-discovery/concepts_brief.md` — **reviewed 2026-11-11** by six Goldfish lenses (design, codebase-details, zoom-out, comprehension, implementation-readiness, structural; direct parallel dispatch after the synthesizer subagent's environment lacked subagent execution). Verdicts: 5 × SHIP WITH CHANGES, 1 × NOT READY (implementation-readiness, on specification gaps — all addressed by adopted resolutions recorded in the brief's Analysis and Key Decisions). Key corrections the review forced: the pre-review draft's `PROBABLE_SAME_AS`/"verified license link" claims were false (name-keyed edges only); 38% of transaction prices are UNBOOKED declared prices (price columns now BOOKED-only); release-scope contradictions resolved by an explicit Goals vs. Non-Goals section; scenario 1 accepted on the Compare grid; `/api/explore` endpoint added to scope; benchmark gate restated with unit-type stratification.
- `docs/UI_COMPONENT_PLAN.md` §6 recommendation (current stack for release 1) was **endorsed by the review**, with one addition adopted: extract the embedded HTML template to static files and vendor pinned CDN assets before any framework decision.

## 8. Handoff

- **Fixes completed:** §1 (13 items, each with verification evidence; tests 18/18).
- **Fixes queued from review (pre-feature):** eager model training, copilot escape-then-markdown + sanitized errors, graph self-link exclusion, guarded param parsing, `allow_nan=False`, `ui/EGM.md` rationale rewording.
- **Features proposed (reviewed):** release-1 scope per the brief's Goals vs. Non-Goals; `/api/explore` contract in the brief's Blocker-1 resolution.
- **Decisions pending:** (a) commit the verified fix pass to `ui-revamp` (awaiting go-ahead); (b) fixture approach for scenario 2 — static mock (recommended) vs demo SQLite DB; (c) template extraction + asset vendoring approval; (d) copilot-on-Explore behavior (hidden vs explicitly bound); (e) BCR/LEGAL_PCWF/TP_PCWF definitions from the pipeline catalog; (f) frontend re-evaluation triggers (statewide ingestion / Ask stage); (g) statewide download-gap audit as a separate follow-on task.
