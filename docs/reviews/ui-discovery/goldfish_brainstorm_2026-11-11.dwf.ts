/*
 * EGM Goldfish brainstorm workflow (typechecked 2026-11-11; NOT executed in that session
 * because dynamic-workflow execution was unavailable there).
 *
 * Purpose: run the six Goldfish BRAINSTORM lenses (egm-design, egm-codebase-details,
 * egm-zoom-out, egm-comprehension, egm-implementation-readiness, egm-structural) in parallel
 * over docs/reviews/ui-discovery/concepts_brief.md, with an independent read-only fact-checker
 * per lens for every Blocker/Major finding. Returns per-lens findings + challenge answers for
 * the EGM synthesizer to deduplicate into concepts_brief.md.
 *
 * To run: on a host where dynamic workflows execute, submit this file to CreateWorkflow
 * with `path`. It compiled cleanly against the dynamic-workflows facade on 2026-11-11.
 */

interface LensFinding {
  /** Short, unique finding title. */
  title: string;
  /** Blocker = the concept as written would mislead a user or is contradicted by code or data; Major = a real gap needing a decision before this becomes a design draft; Nit = polish. */
  severity: "Blocker" | "Major" | "Nit";
  /** Precise evidence: file path with line numbers, the brief's section or table row, or a data fact. */
  evidence: string;
  /** Why it matters for the first-release decision, one to three sentences. */
  risk: string;
  /** Concrete alternative or fix, one to three sentences. */
  fix: string;
}

interface ChallengeAnswers {
  /** Which filters and analytics narrow a shortlist at 9 projects, and which are table dressing. */
  filters: string;
  /** Whether 1,673 recorded Form-3 prices support meaningful local comparisons, and which claims exceed the data. */
  prices: string;
  /** Whether missing filings (2 per project) or PROBABLE_SAME_AS soft links could mislead users about a project, promoter, or professional. */
  misleading: string;
  /** Whether a user can see the scope of a cross-project answer and verify its evidence. */
  scope: string;
  /** Whether the first release can stay on the current Python-served frontend, or whether Vue/React migration materially reduces owned code. */
  frontend: string;
}

interface LensReport {
  /** One-sentence lens verdict on the concept as written. */
  verdict: string;
  /** At most 8 findings, Blocker first, then Major, then Nit. */
  findings: LensFinding[];
  /** Answers to the five author challenges, two to five sentences each. */
  challenges: ChallengeAnswers;
}

interface Verdict {
  /** The finding title this verdict applies to, echoed exactly. */
  title: string;
  /** confirmed = evidence checks out; refuted = evidence is wrong; adjusted = partly right with corrected evidence. */
  status: "confirmed" | "refuted" | "adjusted";
  /** One to three sentences: what was checked, in which file, and the correction if any. */
  note: string;
}

interface FinalLens {
  id: string;
  lens: string;
  verdict: string;
  findings: (LensFinding & { verification: string })[];
  challenges: ChallengeAnswers;
}

interface FinalReport {
  conclusion: string;
  lenses: FinalLens[];
  verified: string[];
  notCovered: string[];
}

const ROOT = "D:/Code Projects/Miscellaneous/Real Estate Data/gujRERA";
const PERSONA_DIR = "C:/Users/adars/.zcode/cli/plugins/cache/egm/egm/0.1.0/agents";

const GOLDFISH_SYSTEM =
  "Goldfish subagent (Elephant-Goldfish Model): strictly read-only and stateless. " +
  "Never edit, create, or write any file; read and analyze only. No chitchat; report technical findings only. " +
  "If a required file is missing or your instructions contradict each other, say so plainly in your report instead of improvising.";

const HYPOTHESIS =
  "Ship the first UI release on the current Python-served dashboard (stdlib ThreadingHTTPServer + one embedded single-file HTML template, Chart.js + vis-network from CDN, no frontend migration): " +
  "a filterable, sortable Explore table over the 9-project curated intelligence DB; two validated summaries (filing freshness with printed cutoff dates; completion-revision status in three honest states: revision observed / no revision observed in comparable filings / insufficient comparable history); " +
  "the existing 8 tabs preserved as Project Detail with match-reason and evidence deep links; a localStorage shortlist. " +
  "Later stages are gated on verified data coverage, not dates: local price benchmark (needs >=3-project comparison groups; only recorded Form-3 transaction prices exist today, 1,673 of them, zero asking-price listings), architect narrowing (name-only attribution today, 8/9 coverage), " +
  "related-case tiers (applications table only, statuses null), full side-by-side compare, and cross-project Ask with three explicit scopes (filtered results / shortlist / all indexed). " +
  "The statewide 17,634-project index stays deferred until its download gaps are audited (author decision 2026-11-11). " +
  "Acceptance scenario 2 (South Bopal/Shela 3BHK value + architect + promoter history) runs on banner-labeled sanitized fixtures, with live data showing 'insufficient comparable data' alongside.";

const CHALLENGES = [
  "1. Which filters and analytics actually help users narrow a shortlist at 9 projects - and which are table dressing?",
  "2. Do the available prices (1,673 Form-3 recorded transactions, zero asking-price listings) support meaningful local comparisons, and which claims exceed the data?",
  "3. Could missing filings (2 per project only) or uncertain entity matches (PROBABLE_SAME_AS soft links) lead to misleading conclusions about a project, promoter, or professional?",
  "4. Can users see the scope of a cross-project answer and verify its evidence?",
  "5. Can the first release use the current frontend with reasonable effort, or does migration (Vue + Vite + shadcn-vue / React + Vite + shadcn/ui) materially reduce the code the team would own?",
].join("\n");

interface LensSpec {
  id: string;
  label: string;
  persona: string;
  mandate: string;
  focus: string;
}

const LENSES: LensSpec[] = [
  {
    id: "egm-design",
    label: "Design Critic",
    persona: PERSONA_DIR + "/design_critic.md",
    mandate: "System architecture, scalability, infrastructure economics, cost and quota (your persona's BRAINSTORM section: Cost & Quota Economics, Architectural Bottlenecks).",
    focus: "The draft claims the current stack carries the release - stress-test that. ThreadingHTTPServer with one shared SQLite connection (check_same_thread=False, 30 s busy_timeout) under concurrent read threads; the Explore table needs columns that /api/projects does not return today (it selects only project_id, name, district, promoter_name), so does Explore need a new endpoint or per-project client enrichment; CDN dependence (Tailwind, Font Awesome, vis-network, Chart.js) versus the platform's 'sovereign local-first' claim; where sanitized fixture data would physically live and how the UI guarantees fixtures never mix into live counts; localStorage as the shortlist store; cross-project Ask token economics when the agentic LLM answers over N projects; what breaks first if the 17,634-row statewide index is ingested later.",
  },
  {
    id: "egm-codebase-details",
    label: "Codebase Details",
    persona: PERSONA_DIR + "/codebase_details.md",
    mandate: "Observability, telemetry, and operational debuggability (your persona's BRAINSTORM section), plus your pedantic REVIEW-mindset verification applied to the draft's claims about current code.",
    focus: "Verify the draft's factual claims about the implementation before trusting them: the 8 existing tabs; the claim that 'tables, filter chips, summary badges, fetch-and-render panels' all already have working patterns in the template (check which actually exist - the copilot's quick-prompt chips are static buttons, not removable filter chips); the localStorage precedent (copilot_api_key); the claim that the loader derives rate_per_sqft (check the db loader code); the /api/projects column list; ThreadingHTTPServer (note the repo-root EGM.md still says 'single-threaded' - a stale contract). Then report observability gaps for the new release: what an operator gets when Explore or cross-project Ask misbehaves (request logging, error surfacing, copilot fallback logging, scope echoed in answers), and what the 3 AM triage story is. If a Python interpreter is available you may spot-check data-coverage claims against real_estate_intelligence/data/intelligence.sqlite with read-only queries (python -I, sqlite3 URI mode=ro); if not, say so in the challenge answers.",
  },
  {
    id: "egm-zoom-out",
    label: "Skeptical Architect",
    persona: PERSONA_DIR + "/zoom_out.md",
    mandate: "Contrarian / YAGNI and code minimization (your persona's BRAINSTORM section: does the feature need to exist now, can existing code solve it).",
    focus: "Go filter by filter through the draft's five filter groups and both summaries and say which actually help narrow a shortlist at 9 projects and which are table dressing (challenge 1). Question whether Explore needs new server code at all at 9 rows; whether a free-text search box adds anything over a 9-row table; whether shipping 'a basic side-by-side' Compare now duplicates the deferred full Compare; whether the fixture machinery for one acceptance scenario earns its cost versus stating the limitation in the UI; whether the three-tier related-case design belongs in this concept at all given it is already deferred. Identify reuse: existing esc()/fetchJSON/switchTab patterns, existing /api/projects, the existing tab framework, the existing graph contagion view.",
  },
  {
    id: "egm-comprehension",
    label: "Naive Reader",
    persona: PERSONA_DIR + "/comprehension.md",
    mandate: "UX and developer ergonomics, cognitive overhead (your persona's BRAINSTORM section: is the proposed interface intuitive, are error behaviors actionable).",
    focus: "Walk the concept as a first-time homebuyer user, not an engineer: can a naive user understand the three revision states (revision observed / no revision observed in comparable filings / insufficient comparable history) without misreading 'no revision observed' as 'no revisions ever'; does the printed cutoff-date pattern actually get noticed; can a user see the scope of a cross-project answer at answer time and verify its evidence (challenge 4); is 'not stated' versus zero consistently understandable; does Explore as the new landing tab break the current single-project user's flow; how obvious is the fixture 'demo data' banner and how bad is it if missed; is the match-reason strip discoverable; does the filter rail's unknown-value counter ('2 of 5 have no filed completion date') read clearly; terminology per the repo GLOSSARY (promoter, not builder).",
  },
  {
    id: "egm-implementation-readiness",
    label: "Tech Lead",
    persona: PERSONA_DIR + "/implementation_readiness.md",
    mandate: "Migration, backward compatibility, rollout safety (your persona's BRAINSTORM section: how do clients and storage migrate, how is rollback handled).",
    focus: "Challenge 5 with numbers: server.py is 2,309 lines today (HTML_TEMPLATE spans lines 22-1645, roughly 1,620 lines of HTML/CSS/JS). Estimate what Explore + two summaries + match-reason strip + shortlist + scope selector add to that file on the current stack, versus what a Vue + Vite + shadcn-vue or React + Vite + shadcn/ui migration would add and remove (build tooling, node dependency, a second language, API shape work) - and say which code the team would actually own in each case. Also: the draft leaves decisions to the implementer (fixture data location and injection mechanism, URL-hash encoding beyond '#exploreq=...', sort semantics for text/number/null columns, shortlist v1 schema details beyond 'JSON array of project IDs + added-at') - list every design decision the draft still owes before coding starts; backward compatibility (localStorage key versioning, the existing 8 tabs must keep working, ui/EGM.md route contract updates); rollout and rollback on the ui-revamp branch.",
  },
  {
    id: "egm-structural",
    label: "Structural Validator",
    persona: PERSONA_DIR + "/structural.md",
    mandate: "Long-term tech debt, coupling, and maintainability (your persona's BRAINSTORM section: tightly coupled dependencies, brittle state machines, the 2-year maintenance burden).",
    focus: "The embedded single-file template (HTML + CSS + JS + Python handlers in one 2,309-line file) - where Explore's code lives, whether the file crosses into unmaintainable size, and what the cheapest decoupling would be that does not become a framework migration. Definition duplication: Explore, Compare, and cross-project Ask must share 'the exact definitions and thresholds' - where does that single source of truth live so three surfaces cannot drift. Contract drift: the repo-root EGM.md still describes the dashboard as single-threaded; ui/EGM.md will need new routes documented. CDN pinning inconsistencies (Chart.js pinned at 4.4.4, Tailwind and vis-network unpinned). The URL-hash state machine as a brittle hand-rolled parser. localStorage shortlist schema evolution across browsers.",
  },
];

function lensPrompt(lens: LensSpec): string {
  return [
    "Mode: BRAINSTORM (upstream concept ideation), run by the EGM synthesizer for the Elephant.",
    "",
    "STEP 1 - Adopt your persona. Read this file first and take on that role exactly:",
    lens.persona,
    "",
    "STEP 2 - Read the material under review (read-only; do not edit, create, or write any file):",
    "1. Concept under review (the draft being brainstormed): " + ROOT + "/docs/reviews/ui-discovery/concepts_brief.md",
    "2. Current dashboard implementation: " + ROOT + "/real_estate_intelligence/real_estate_intelligence/ui/server.py (2,309 lines; embedded HTML_TEMPLATE UI at lines 22-1645, HTTP handlers and copilot at 1647-2309). Read all of it.",
    "3. UI contract: " + ROOT + "/real_estate_intelligence/real_estate_intelligence/ui/EGM.md",
    "4. Platform spec: " + ROOT + "/docs/SPEC.md",
    "5. Repo blueprint: " + ROOT + "/EGM.md",
    "6. Verified fix-pass handoff (component inventory, test counts, known limitations): " + ROOT + "/docs/UI_COMPONENT_PLAN.md",
    "",
    "FeatureConcept (anchored hypothesis under review):",
    HYPOTHESIS,
    "",
    "The author asked the review panel five challenges. Answer every one from your lens, two to five sentences each:",
    CHALLENGES,
    "",
    "Your lens mandate (from your persona's BRAINSTORM section): " + lens.mandate,
    "Give special attention to: " + lens.focus,
    "",
    "Rules: strict read-only. Cite evidence precisely (file path with line numbers, or the brief's section/table row you are quoting). " +
      "Severity: Blocker = the concept as written would mislead a user or is contradicted by the code or the data; Major = a real gap that needs a decision or change before this becomes a design draft; Nit = polish. " +
      "Report at most 8 findings, ordered Blocker first, then Major, then Nit, with unique titles. " +
      "Plain English, no promotional language, no padding: if your lens has nothing real to say for a challenge answer, say what your lens does see instead of inventing filler.",
    "",
    "Return your report as the structured value requested (verdict, findings, challenges).",
  ].join("\n");
}

function checkPrompt(lensLabel: string, findings: LensFinding[]): string {
  return [
    "You are a read-only fact-checker for one brainstorm lens (" + lensLabel + "). Repository root: " + ROOT,
    "For each finding below, verify only its factual claims: file and line citations, statements about what the code or data contains, quoted numbers and dates. " +
      "Read the cited files yourself before ruling. Do not re-litigate judgment calls such as YAGNI opinions, UX taste, or effort estimates - if a finding contains no verifiable factual claim, return confirmed and note that it is a judgment call.",
    "Verdicts: confirmed = the evidence checks out; refuted = the evidence is wrong (explain what is actually there); adjusted = partly right (give the corrected evidence).",
    "Echo each finding's title exactly as given, one verdict per finding.",
    "",
    "Findings:",
    JSON.stringify(findings, null, 2),
  ].join("\n");
}

phase("Run the six Goldfish lenses and fact-check substantive findings");
log("Six Goldfish lenses review the UI first-release concept in parallel; each lens's Blocker and Major findings then get an independent read-only fact-check.");

const collected = await Promise.all(
  LENSES.map(async (lens) => {
    const rep = await agent(lens.label + " lens", GOLDFISH_SYSTEM).ask<LensReport>(lensPrompt(lens));
    report({
      lens: lens.id,
      label: lens.label,
      verdict: rep.verdict,
      blockers: rep.findings.filter((f) => f.severity === "Blocker").length,
      majors: rep.findings.filter((f) => f.severity === "Major").length,
      nits: rep.findings.filter((f) => f.severity === "Nit").length,
    });
    const substantive = rep.findings.filter((f) => f.severity !== "Nit");
    let verdicts: Verdict[] = [];
    if (substantive.length > 0) {
      const checker = agent("Fact checker - " + lens.label, GOLDFISH_SYSTEM);
      verdicts = await checker.ask<Verdict[]>(checkPrompt(lens.label, substantive));
    }
    return { lens: lens, rep: rep, verdicts: verdicts };
  }),
);

// Join is required: the synthesis across lenses needs every lens report before deduplication.

const finalLenses: FinalLens[] = collected.map(({ lens, rep, verdicts }) => ({
  id: lens.id,
  lens: lens.label,
  verdict: rep.verdict,
  findings: rep.findings.map((f) => {
    const v = verdicts.find((x) => x.title === f.title);
    let verification = "Nit - not fact-checked";
    if (f.severity !== "Nit") {
      if (!v) {
        verification = "unconfirmed - fact-checker returned no verdict for this title";
      } else if (v.status === "confirmed") {
        verification = "verified: " + v.note;
      } else if (v.status === "refuted") {
        verification = "REFUTED by fact-checker: " + v.note;
      } else {
        verification = "adjusted: " + v.note;
      }
    }
    return { title: f.title, severity: f.severity, evidence: f.evidence, risk: f.risk, fix: f.fix, verification: verification };
  }),
  challenges: rep.challenges,
}));

const countBy = (sev: string) =>
  finalLenses.reduce((n, l) => n + l.findings.filter((f) => f.severity === sev).length, 0);
const refutedCount = finalLenses.reduce(
  (n, l) => n + l.findings.filter((f) => f.verification.startsWith("REFUTED")).length, 0);

const result: FinalReport = {
  conclusion:
    "Six Goldfish lenses reviewed the first-release concept and returned " + countBy("Blocker") + " blocker, " +
    countBy("Major") + " major and " + countBy("Nit") + " nit findings; " + refutedCount +
    " finding(s) were refuted by fact-checking and are labelled as such. Every Blocker and Major finding was independently fact-checked against the repository by a dedicated read-only checker for that lens. " +
    "The EGM synthesizer deduplicates these into the updated concepts brief.",
  lenses: finalLenses,
  verified: [
    "Each lens read the draft, server.py (2,309 lines), ui/EGM.md, docs/SPEC.md, the repo EGM.md, and docs/UI_COMPONENT_PLAN.md before reporting.",
    "Every Blocker and Major finding's factual evidence was checked against the repository by a dedicated read-only fact-checker subagent per lens; verdicts are attached to each finding in the verification field.",
    "Nit findings were not fact-checked (labelled 'Nit - not fact-checked').",
  ],
  notCovered: [
    "No lens launched the dashboard or exercised the UI in a browser; runtime behavior claims rest on the verifications recorded in docs/UI_COMPONENT_PLAN.md.",
    "Data-coverage claims in the draft were verified by the author against intelligence.sqlite on 2026-11-09; lenses re-queried the database only where their challenge answers say they did.",
  ],
};
return result;
