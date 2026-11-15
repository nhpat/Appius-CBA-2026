# Foundation Prospector — Status Report for Client Review

Prepared 2026-11-14. Covers the first real-data pass since the project moved off synthetic
fixtures: real IRS data loaded, five parallel workstreams run against it, two concrete
model/code fixes shipped. This report is in two parts: decisions we need your input on,
and a summary of everything completed so far with pointers to the detailed write-ups.

---

## Part 1 — Decisions needed from you

### 1. How should we resolve the peer/seed name-matching threshold?

The tool checks whether a foundation has funded a client's peer organizations, and
sanity-checks the whole model against a list of known real foundations ("validation
seeds"). Both checks work by comparing organization names with a similarity score and a
cutoff — currently 90 for peers, 95 for seeds.

**The problem:** no single cutoff works. Tested against 14 known real name-change pairs
and 26 pairs of genuinely different organizations with similar names:

- At the current 95 cutoff: catches only **1 of 14** real aliases — it misses, for
  example, the New York Health Foundation's own 2022 name change (scores 89.7%, just
  below the line) — but makes **0 false matches**.
- At 90 (the peer-matching default): still only 1 of 14 aliases, but now makes
  **1 false match**: Connecticut Public Health Association is confused with Connecticut
  Association of Health Plans (90.4% similarity) — a different organization that could
  wrongly add credit to a funder's score.
- Independently, we found the **"Park Foundation" validation seed is currently matched
  to "Spark Foundation"** (96.8% similarity) — a different organization in Massachusetts.
  The real Park Foundation isn't in this data batch at all.

**Recommended fix:** manually look up and store the real IRS EIN for each of the ~31
names on the peer/seed lists (a one-time, few-hour task), so those specific checks become
exact instead of a similarity guess. For anything not on those curated lists, use a
two-tier threshold (auto-accept ≥95, human review 89–95, reject below) instead of one
cutoff.

**What we need from you:** sign-off to spend the time curating EINs for the peer/seed
lists, and confirmation that the two-tier review approach is acceptable for everything
else, or a different priority if this isn't worth the time yet given the broader data
limitations below.

### 2. Should "mission fit" block a funder from ranking, even if everything else scores well?

This was flagged as an open question before any real data existed. We can now show it's a
real, large effect: **72 of 83 NYSPHA** and **39 of 66 Appius** Tier B/C funders have a
mission-fit score under 0.3 out of 1.0 — meaning most of the mid-tier list is reaching
that tier on geography, size, and activity alone, with little to no actual thematic
overlap with the client's work.

**What we need from you:** a decision on whether mission fit should act as a gate (e.g.,
cap the tier, or require a minimum mission score to reach Tier B or above), and if so,
what the cutoff should be. This is a scoring-philosophy call, not something we can decide
from the data alone — the data just confirms the question is live, not hypothetical.

### 3. How much real data should the model have in before anyone acts on its output?

Everything below is built on **one month** of real IRS filings (the September 2026
processing batch). That's enough to prove the pipeline runs correctly end to end, but
most foundations file once a year, so a lot of real funders — including most of the known
validation seeds — simply aren't in this slice yet. There are currently **zero Tier A**
funders for either client, which is a function of data volume, not funder quality.

**What we need from you:** whether to continue ingesting more monthly filings before
treating any ranking as actionable, or whether there's a reason to move forward sooner
(e.g., to unblock other work) despite the thin data.

---

## Part 2 — What's been completed (for your review)

### Real data is in
We moved off the synthetic test fixtures and loaded real government data: the IRS
Business Master File (NY plus five neighboring states), Census geography data, USDA rural
codes, and one month of real 990-PF/990 filings (5,433 filings, 59,590 individual grant
lines). The recipient-matching rate on NY grant dollars is **61.2%**, just above the 60%
target set at project start.

### Theme/mission-fit model — rewritten and measured
The keyword rules that decide what a grant's purpose is "about" were rewritten against
200+ hand-labeled real grant lines, after the original rules were found tagging things
like "Branches" as agriculture and international aid organizations as substance-use
programs. Measured improvement: **precision 0.32 → 0.76, recall 0.40 → 0.65** on a held-out
test set. Full write-up: `analysis/taxonomy_eval/README.md`. Every change and its
reasoning is logged in `docs/MODEL_CHANGELOG.md`.

### Rural definition — reviewed and decided
We compared the current rural classification (USDA RUCA codes 4–10) against the federal
government's own HRSA rural-health definition. The two disagree on about 3,000 of 41,000
ZIP codes nationally, but the practical effect on current scores is small (0–1 tier
changes across both client lists). **Decision: keep the current RUCA-based definition**
for now rather than adopt HRSA's more complex methodology, with the option to add HRSA's
definition as a separate, configurable measure later if federal rural-health alignment
becomes more important. Full write-up: `docs/MODEL_CHANGELOG.md` (2026-11-11 entry).

### Reporting output and the quarterly handoff — tested and fixed
We tested whether someone with no knowledge of the code could run the quarterly refresh
process, and found it couldn't be done: the documented command crashed on a clean setup,
and pointing it at a missing database produced a fake, fabricated result with no error.
Both are now fixed and re-verified. We also fixed two readability problems in the Excel
output (long text fields were unreadable, and several score columns were unlabeled in a
way that could be misread as point values rather than the 0–1 scale they actually are).
Still open and tracked: the Excel files don't yet explain what the warning flags mean, and
don't warn the reader that the data covers only one month — both are quick additions we
can make next. Full write-up: `docs/reporting_qa/FINDINGS.md` (plain-English version in
`docs/reporting_qa/SUMMARY.md`).

### A concrete bug found in the "restricts lobbying" flag
This flag is currently wrong 100% of the time it fires (3 for 3 cases checked) — it
triggers on the word "political" anywhere in a foundation's restrictions text, including
standard language every charity carries ("no grants to political campaigns"), not actual
lobbying restrictions. This is a quick fix (narrow the keyword) once prioritized.

### Everything above, shared
The real database built from this month's filings has been shared via the team Drive
folder so the rest of the team can work from the same real data without each re-running
the multi-step download process individually.

---

## Bottom line

The infrastructure went from "can't be handed off" to "runs end to end and is
documented" this cycle. Model trustworthiness improved meaningfully (taxonomy accuracy
roughly doubled) but isn't finished, and two of the three open decisions above
(mission-as-gate, how much data before acting) are genuinely yours to make, not something
more engineering time resolves on its own.
