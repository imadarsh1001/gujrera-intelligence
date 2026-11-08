# EGM Contract Tree Publication

> **Status: EXECUTED AND ARCHIVED (2026-11-09).** This file is the ideation record for one **completed** decision — how to publish the EGM contract tree. It is **not** a pending proposal, and it is **not** an intake source for new work. If an EGM process (`egm-draft`, `egm-brainstorm`, `egm-drift-report`, or any agent) reads it, here is what to think and how to continue:
>
> 1. **What to think:** everything in this brief was decided and executed. The fork below (Plan A hardened full plan vs. Plan B minimal cut) was **resolved: Plan A** — the zoom-out minimal cut was considered and rejected. Do not re-open the questions in the Analysis section; they describe problems that were fixed before execution (gitignore idiom, push refspec, glob staging, unset `git user.name` — all resolved as specified in "Key Decisions").
> 2. **What it produced:** private repo commit `f2d019d` (4 contracts + `.gitignore` idiom), public repo commit `ea80773` (12 contracts + `README.md` contracts section + this audit-trail directory), and branch-safe `push_all` fixes `ae7d517`/`d2d2f06`/`f552c7e` — all live on both remotes. The published `EGM.md` tree is authoritative over anything written here.
> 3. **How to continue the work it means to continue:** the live workstream is (a) improving `README.md` step by step against the published `EGM.md` tree; (b) contract maintenance — when code changes, refresh the affected contracts (drift check → review → `push_all`, which is now branch-safe); (c) new ideas go through a **fresh** `egm-brainstorm` — a new brainstorm overwrites `concepts_brief.md` at the workspace root, never this archived copy. Ground new reviews with `GoldfishContext`: the `EGM.md` tree + `README.md` + `GLOSSARY.md` + the source dirs the idea touches.

* **Author:** Adarsh Patel (per-commit `git -c`; persistent git config untouched)
* **Date:** 2026-11-09

## Overview

Publish the EGM contract tree produced by the bootstrap and six-round review (23 contract files, 96 findings, 94 fixes, all verified against source) to both git remotes: 12 contract files plus 2 review artifacts to the public repo (`gujrera-intelligence`), and 4 contract files to the private repo (`gujrera-pipeline`). Six independent review lenses then attacked the plan. Result: the plan's goal survives, but its mechanics contained four execution blockers — every one confirmed by at least two lenses independently — and one reviewer argues for a much smaller publication. The plan needs hardening before anything is committed.

## Analysis

### Confirmed execution blockers (the plan fails silently as written)

1. **The public push would ship nothing.** Committing on `test1` and then running `git push origin main` pushes the local `main` ref — which does not contain the new commit — and reports "Everything up-to-date." Five of six lenses found this independently, and it is a latent bug in the user's own `push_all.bat`/`push_all.ps1` (`git push origin main` regardless of checked-out branch). The root `EGM.md` even documents this wrong belief as an invariant ("pushing from a non-main branch still targets main"). Fix: commit on `main` directly (test1 and main are identical today, so nothing is lost), or push with the explicit refspec `git push origin test1:main` — and correct the `EGM.md` invariant line before committing it.

2. **The private `.gitignore` exceptions are a no-op, and the naive fix leaks data.** Git cannot re-include a file whose parent directory is excluded: after `data/*`, the line `!data/discovery/EGM.md` does nothing (verified with `git check-ignore`). The "obvious" fix — `!data/discovery/` — would instead un-ignore the whole directory, which contains a 16.4 MB portal bundle, captured API probes with scraped personal data (phone numbers, registration numbers, addresses), and the discovery scripts; one later `git add .` from the push scripts would sweep all of it into the remote. The correct, narrow idiom (matching the file's own existing convention) is three lines, in order: `!data/discovery/`, `data/discovery/*`, `!data/discovery/EGM.md` — and the modified `.gitignore` itself must be part of the commit, or the push leaves a dirty tree with rules that disagree with the tracked files.

3. **The public add command stages 2 of 11 files.** In Git Bash on Windows, `**` in `real_estate_intelligence/**/EGM.md` degrades to a single level (globstar is off by default), so the glob matches only 2 of the 11 subtree contracts; git's own pathspec engine interprets it differently again. Use the explicit 14-path list (or `git add real_estate_intelligence`, verified to contain only the 11 contracts) and check `git status --short` shows exactly 14 files before committing.

4. **Every commit aborts: `git user.name` is unset** (only `user.email` is configured). Either set it once or pass it per commit (`git -c user.name="Adarsh Patel" -c user.email="..." commit ...`).

### Substance objections (what the lenses say is wrong with publishing as planned)

- **The two process artifacts are stale the moment they land.** The drift report says its 9 findings are "recorded for human triage" — all 9 were fixed during the review; it quotes contract text that no longer exists. The goldfish report is 61.6 KB (larger than all 12 public contracts combined), references private paths a public clone cannot have, and uses session vocabulary ("Goldfish", "round", "auto accept") defined nowhere in the repo. Four lenses independently said: move them under `docs/reviews/` (the repo's existing convention), give each a resolution header ("historical record; all findings applied — see the contracts themselves"), or don't publish them at all.
- **The root `EGM.md` does not stand alone in the public repo.** Two of its four Subdirectory links 404 in a fresh public clone, and the repo's own convention (README.md) deliberately describes the private repo in prose without links. Fix before committing: convert the `gujrera_pipeline`/`legacy` entries to non-linked prose, and update its "Root-level files" list (it omits the reports it ships with).
- **The publication publishes 16 of the 23 reviewed contracts.** The 7 `legacy/**/EGM.md` files sit in a gitignored directory, tracked in no repo, yet both reports discuss them and the root contract links one. The plan must state this exclusion explicitly (scope note in the reports, or one line in the plan).
- **"EGM" is defined nowhere in the repository.** No file expands the acronym or says why every directory has one. A first-time visitor cannot tell what these files are. Minimal fix: a one-paragraph README section ("per-directory code contracts, machine-verified against source on 2026-11-09, generated and reviewed via EGM") plus a self-contained commit message.
- **A half-tracked contract misleads.** `data/discovery/EGM.md` would be the only tracked file in a directory of untracked scripts; the private repo's root contract says that directory "contains source code" that clones cannot see. Either track the 3 small discovery scripts (~4 KB total) alongside it, or annotate the contract as covering local-only files.
- **The private contracts are private for a reason.** The `data/` tree holds raw personal-data captures; publishing contracts describing it is defensible but erodes the privacy posture slightly for near-zero external value.

### The strategic fork the lenses exposed

The zoom-out lens argues the minimal cut: publish **11 public subtree contracts + 1 private pipeline-root contract, nothing else** — no reports (session scratch; the fixes are already materialized in the contracts), no root `EGM.md` (documents rooms the public clone doesn't have), no data-contracts, no `.gitignore` changes. That is the smallest defensible publication. Against it: the reports are the only provenance for 94 fixes, and the user explicitly wanted the workspace-level view. The rest of the lenses' fixes make the full publication safe; the fork is the user's to settle.

## Goals vs. Non-Goals

* **In-Scope Goals:** land the verified contract tree on both remotes; keep provenance for the 94 fixes; leave both working trees clean afterward; correct the refspec bug in `push_all` knowledge (if not the scripts themselves).
* **Out-of-Non-Goals (explicitly not in this change):** branch protection, a link-checking CI workflow (flagged as cheap follow-up, not part of this push), maintaining `test1` as a staging branch, publishing the 7 legacy contracts, changing any code or README content beyond the one EGM-definition section the lenses require.

## Alternatives Weighed

* **Original plan (commit 12+2 public, 4 private after two gitignore lines, push origin main):** rejected — four execution blockers (refspec, gitignore no-op, glob degradation, unset identity).
* **Zoom-out minimal cut (11 public + 1 private contract, no reports, no root EGM, no gitignore changes):** viable; rejected-by-default pending the user's fork decision — loses provenance and the workspace view, gains minimalism.
* **`git add -f data/EGM.md data/discovery/EGM.md` (skip gitignore changes):** rejected — leaves committed ignore rules that claim the files are excluded, misleading every future maintainer; `git add -f` also bypasses the accidental-sweep protection the ignore rules provide.
* **`!data/discovery/` alone:** rejected — un-ignores the entire directory, pushing ~20 MB of captured personal-data artifacts on the next `git add .`.
* **Hardened full plan (this brief's recommendation):** original scope with every blocker fixed, reports relocated to `docs/reviews/` with resolution headers, root EGM.md public-scoped, EGM defined in README and commit messages, private-repo push first.

## Key Decisions & Staging for Next Steps

1. **Fork decision (user):** hardened full plan vs. zoom-out minimal cut.
2. **Author identity (user):** `git user.name` is unset; prior commits say "Adarsh Patel" — confirm, or it will be passed per-commit via `git -c`.
3. **Mechanics locked by evidence (non-negotiable in either fork):** explicit refspec or commit-on-main; explicit 14-path add list with a `git status --short` count check; private repo: append `!data/EGM.md`, `!data/discovery/`, `data/discovery/*`, `!data/discovery/EGM.md` (in that order) and commit the `.gitignore`; `git check-ignore` verification before staging; private repo pushed before public; preflight `git fetch` + ahead/behind check; abort and report on any failure — never force-push, never fall back to `git add .` scripts.
4. **If full plan:** relocate both reports to `docs/reviews/`, prepend resolution headers, edit root `EGM.md` (prose for private entries, updated root-file list, corrected push-refspec invariant), add the EGM-definition paragraph to `README.md`, use self-contained conventional commit messages.
5. **Post-push verification (made concrete):** `git status --porcelain` empty in both repos; `git ls-tree -r origin/main --name-only | grep EGM.md` returns 14 (public) / 4 (private) + `.gitignore`; structural link check re-run.
