# Workstream 5 — Reporting / QA findings

**Original run:** fresh clone of `nhpat/Appius-CBA-2026` @ `700103f`; shared `prospector.db` (batch 2026_TEOS_XML_09A); Python 3.15 venv. Run date 2026-11-11.

**Re-verified:** 2026-11-13, against `main` @ `5d0f0b3` — after the theme-taxonomy rewrite (Known Issue #2), rural-definition validation (Known Issue #6), and a first pass of fixes to this workstream's own T1/T2/T5/T6/X5 findings landed. Re-checked with the same `inspect_reports.py` against freshly regenerated reports. Status markers below (**FIXED**, **STILL OPEN**, **NUMBERS UPDATED**) reflect this re-check, not the original run.

**Bottom line (updated)**
- Setup works: 33/33 tests pass (was 27; taxonomy/peer-seed tests added), the NY match rate is still 61%, both reports generate.
- The handoff command crash (T1/T2) and silent-junk-on-empty-db (T6) are **FIXED** as of `5d0f0b3`.
- The 0–1 vs. points column-labeling issue (X5) is **FIXED**.
- The Excel files still don't explain their flags (X1) or warn about data coverage (X2) — **STILL OPEN**.
- The Validation tab still shows the **false seed match** (Park Foundation → Spark Foundation, X9) — **STILL OPEN**, unaffected by the taxonomy/rural work since it's peer/seed-matching code.

---

## 1. Refresh handoff test

Command (now documented with quoting — see note below): `python -m prospector refresh --client nyspha appius --zips 'data/raw/*.zip'`

| # | Test | Original result | Re-check (2026-11-13) |
|---|---|---|---|
| T1 | zsh (macOS default), exactly as originally documented (unquoted) | ❌ `zsh:1: no matches found` | **Still fails exactly this way if unquoted** — this is a shell-level abort before Python runs, so no amount of Python code fixes it. **FIXED differently than recommended**: the documented command itself now quotes `--zips` (README, CLI docstring), which avoids the shell-level failure; `cmd_refresh` also now expands globs via `glob.glob()` so a quoted pattern with zero matches degrades gracefully instead of crashing. |
| T2 | bash, exactly as documented | ❌ `FileNotFoundError` | **FIXED.** Re-ran unquoted in bash with a non-matching pattern: now prints `No zips matched [...]; rescoring existing data only.` and proceeds. |
| T3 | No `--zips`, live Grants.gov | ✅ ~3.6s | ✅ Still works, ~29s this time (cold Grants.gov cache) |
| T6 | Clean/empty db | ❌ Silent junk, fake Tier A | **FIXED.** Re-ran against a fresh empty db: now exits immediately with `'bmf' is empty. Run 'load-reference' first, or use the shared data/prospector.db -- refusing to score against an empty reference table.` |

**Recommendation (3) still open:** the README's quarterly-refresh section doesn't explicitly say the handoff assumes the pre-built `data/prospector.db` — the T6 fix now makes that assumption loud and clear at runtime (a real error message) rather than silent, but a proactive doc note is still worth adding.

**Recommendation (4) — both small doc fixes landed:** `config/model.yaml`'s header now says `report`, not the nonexistent `score` command. CLI docstring's refresh example now lists both clients and the quoting caveat.

## 2. Excel output — every tab

Still: Read Me, Prospects, Validation, Dropped, Federal, and (Appius) Grantee Leads (INTERNAL, red tab). Header styling, frozen header, autofilter, money/pct formats, tier colors all still work, now plus wrap-text on data cells (see X-new below).

### Read Me
| # | Sev | Status | Issue |
|---|---|---|---|
| X1 | High | **STILL OPEN** | No flag legend. Current NYSPHA flag counts (re-measured): `preselected_only` 362, `vague_purpose` 150, `grantee_size_unknown` 132, `new_grantee_rate_assumed` 116, `oversized_hand_review` 13, `public_charity_schedule_I` 12, `rural_data_missing` 6, `restricts_lobbying` 3. (`vague_purpose` count moved from 100→150 — expected, the taxonomy rewrite changed how many lines get tagged "vague" instead of a real theme.) |
| X2 | High | **STILL OPEN** | No data-coverage caveat — still one IRS processing month, still no Tier A anywhere, most validation seeds still "not in data yet." |
| X3 | Medium | **STILL OPEN** | "Tabs" line still doesn't mention Grantee Leads for Appius. |
| X4 | Check | **STILL OPEN** | Gmail-label reference unchanged. |

### Prospects
| # | Sev | Status | Issue |
|---|---|---|---|
| X5 | High | **FIXED** | All six component columns now labeled "(0-1)" consistently (`Geography (0-1)`, `Size (0-1)`, `Peer (0-1)`, `Openness (0-1)`, `Activity (0-1)`, alongside the pre-existing `Mission (0-1)`). |
| X6 | Medium | **STILL OPEN** | Score format is still `'0.00'` — confirmed `62.2` displays with the general float format, not a clean single decimal. |
| X7 | Medium | **STILL OPEN** | `new_grantee_rate` still computed, still not exported as a column. |
| X8 | Low | not re-checked | — |
| X-new | — | **FIXED (not in original list)** | Data cells had no `wrap_text` — long fields like "How to apply" (up to 1,068 chars) and "Top in-state recipients" rendered as unreadable single-line overflow. Now wrapped. |

### Validation
| # | Sev | Status | Issue |
|---|---|---|---|
| X9 | High — false match | **STILL OPEN** | Confirmed again via `inspect_reports.py`: `seed: Park Foundation -> THE SPARK FOUNDATION INC (DROPPED: average giving $32,743 under $250,000)`. Unaffected by the taxonomy/rural work — this is peer/seed-matching code (Known Issue #4), unchanged since the original run. |
| X10 | Note | unchanged | Still expected given one month of data. |

### Dropped
Re-measured: 4,228 "average giving under threshold" + 601 "no grants in NY" = 4,829. **Identical** to the original run — confirms the hard filters are untouched by the taxonomy/rural changes, as expected (mission and rural don't gate these filters).

### Federal
| # | Sev | Status | Issue |
|---|---|---|---|
| X11 | Medium | **STILL OPEN** | Opens/Closes still plain text. Blank close date: 134/188 NYSPHA (was 135/188), 94/210 Appius (was 95/209) — essentially unchanged, small drift likely from the live API's own listing churn between runs. |
| X12 | Medium | **STILL OPEN, re-confirmed** | 25 NYSPHA rows (22 Appius) still opened before 2024 but marked "posted." The exact same "State Veterans Home Construction Grant Program" (opened 2010) example still appears for NYSPHA, found by the same overly broad keyword. |
| X13 | Low | **STILL OPEN** | Confirmed via script: `hyperlinked: False`. |
| X14 | Medium | not re-checked | — |

### Grantee Leads (Appius, INTERNAL)
**NUMBERS/EXAMPLES UPDATED — likely resolved, but not certain.** The original two named examples ("international clean-water charity tagged `substance_use`," "housing nonprofit tagged `rural_health`") can't be matched to specific orgs since the original write-up didn't record EINs, and the Grantee Leads list itself is now a different set of 6 organizations (the taxonomy rewrite changed mission tagging broadly enough to reshuffle who qualifies as a lead). Current tags on today's list (`human_services` × 5, `behavioral_health` × 1) all look plausible given the org names (e.g., "Hudson Valley Clubhouse" → `behavioral_health` is correct — "Clubhouse" is a recognized psychiatric rehab model). **No obviously wrong tag survives in the current list**, consistent with this category of error being a target of the taxonomy rewrite — but this is circumstantial, not a confirmed fix, since the original bad examples are gone rather than verified corrected.

## 3. Tier B/C flag spot-check (re-run against current data)

| Funder (client, tier, score) | Flags | Status |
|---|---|---|
| John A Hartford Foundation (NYSPHA, Tier B, 57.6) | `new_grantee_rate_assumed, restricts_lobbying` | **STILL a false positive**, same trigger phrase ("...a state or political subdivision thereof"), confirmed via re-run of the spot-check script. |
| Evelyn S and K E Barrett Fdn | `restricts_lobbying` | **STILL fires on "Political campaigns"** — standard 501(c)(3) boilerplate, not a real lobbying restriction. |
| William T Kemper Fdn | `restricts_lobbying` | **STILL fires on "politically partisan purposes"** — same `political` keyword issue, still 3 for 3 false positives on this flag across both reports. |
| NYSPHA mission-gate pattern | — | **NUMBERS UPDATED**: **72 of 83** NYSPHA Tier B/C funders now have mission < 0.3 (was 73 of 103 — fewer total B/C funders post-taxonomy-rewrite, but the proportion with weak mission fit is just as dominant). Newly measured for Appius: **39 of 66**. Known Issue #3 (mission isn't a gate) is still just as real in the current data. |

## Flags for other workstreams (not fixed here, per team ground rules)
- **#2 Peer/seed:** Park → Spark false match (X9) — still unresolved, still a clean example of 95 being too loose for short/common foundation-name words ("park" vs. "spark"). `validate()` still hard-codes 95 instead of reading `model.yaml`.
- **#3 Taxonomy / model owner:** `lobbying_keywords` entry `political` is still 3-for-3 false positives in the current data — unaffected by the theme-taxonomy rewrite, since lobbying keywords are a separate config list in `model.yaml` that wasn't touched by that PR.
- **Model owner:** mission-gate question (Known Issue #3) re-confirmed on current data: 72/83 NYSPHA and 39/66 Appius B/C funders have mission < 0.3.
- **#4 Rural:** unaffected by this re-check; rural validation was handled separately (see `docs/MODEL_CHANGELOG.md`, 2026-11-11 entry — decision was to keep RUCA 4–10).
