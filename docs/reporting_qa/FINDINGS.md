# Workstream 5 — Reporting / QA findings

**Setup tested:** fresh clone of `nhpat/Appius-CBA-2026` @ `700103f`; shared `prospector.db` (batch 2026_TEOS_XML_09A); Python 3.15 venv.
**Run date:** 2026-11-11. To re-check a workbook: `python docs/reporting_qa/inspect_reports.py outputs/<file>.xlsx`. Reports regenerated today, so the files are named `*_2026-11-11.xlsx` (the `report` command stamps the run date).

**Bottom line**
- Setup works: 27/27 tests pass, the NY match rate is 61%, and both reports generate.
- The **handoff command fails as written** in both zsh and bash.
- With no db, it gives no error and **produces junk reports, including a fake Tier A funder**.
- The Excel files are readable, but they **don't explain their flags or score columns**.
- The Validation tab currently shows a **false seed match** (Park Foundation → Spark Foundation).

---

## 1. Refresh handoff test

Command: `python -m prospector refresh --client nyspha appius --zips data/raw/*.zip`

| # | Test | Result |
|---|---|---|
| T1 | zsh (macOS default), exactly as documented, shared-db setup | ❌ `zsh:1: no matches found: data/raw/*.zip`. Python never runs. |
| T2 | bash, exactly as documented | ❌ Traceback: `FileNotFoundError: [Errno 2] No such file or directory: 'data/raw/*.zip'` |
| T3 | Same command **without** `--zips`, live Grants.gov | ✅ Runs in ~3.6 s; NYSPHA 478 scored (B 6 / C 97 / Watch 375), 188 federal; Appius 478 scored (B 1 / C 62 / Watch 415), 209 federal |
| T4 | Zip present (fixture XMLs zipped), on a **copy** of the db | ✅ Ingests 17 returns / 52 grants, re-matches, and rescores |
| T5 | Same zip run a second time | ✅ Safe to re-run: `saved 0, skipped 17`, and tiers are unchanged |
| T6 | Clean clone, **no db file** | ❌ **No error, junk output.** It creates an empty db, matches 0 of 62 grants, and still writes a report showing **1 Tier A** funder. With no BMF loaded it also ingested 3 extra 990s that should have been filtered out (ignored 1 vs 4 in T4). |
| T7 | Side effect seen in T6 | ⚠️ The output path is `outputs/<client>_prospects_<today>.xlsx` no matter what `--db` points at, so T6 **overwrote today's real NYSPHA report**. I regenerated it afterward. |

The shared db was confirmed byte-identical after all tests (`cmp`).

**Fixes to recommend** (code owners decide):
1. Expand globs inside Python (`glob.glob`) and print "no new zips; rescoring existing data" when nothing matches. This fixes T1, T2, and also Windows, where PowerShell/cmd never expand `*.zip`.
2. Refuse to run when the `bmf` or `zip_geo` tables are empty, with a message pointing to `load-reference` or the shared db (fixes T6).
3. README: say that the handoff assumes the pre-built `data/prospector.db`. A from-scratch build still needs manual steps (`scripts/get_reference.py` plus a **hand download** of the USDA RUCA file).
4. Small doc fixes:
   - The `config/model.yaml` header tells you to run `python -m prospector score`, but that command doesn't exist (it should be `report`).
   - The CLI docstring's refresh example lists only `nyspha`.

## 2. Excel output — every tab

Both workbooks have: Read Me, Prospects, Validation, Dropped, Federal. Appius also has Grantee Leads (INTERNAL), with a red tab. Header styling, frozen header row, autofilter, `$#,##0` money and `0%` share formats, and the tier colours (B yellow / C peach / Watch grey) all work.

### Read Me
| # | Sev | Issue |
|---|---|---|
| X1 | **High** | **No flag legend.** Read Me says flags "mark gaps or traps" but never defines any of the 9 codes. Counts in the NYSPHA file: `preselected_only` 362, `grantee_size_unknown` 132, `new_grantee_rate_assumed` 116, `vague_purpose` 100, `oversized_hand_review` 13, `public_charity_schedule_I` 12, `rural_data_missing` 6, `restricts_lobbying` 3. A first-time reader can't act on these. |
| X2 | **High** | **No data-coverage caveat.** It says "Tax years 2023-2025" and "patterns over several years", but the data is a single IRS processing month, and 98% of funders (5,207/5,307) have exactly one tax year. All 6 NYSPHA and 8 Appius validation seeds came back "not in data yet" or dropped. Read Me should name the source batch(es) and warn that the lists are thin. |
| X3 | Medium | The "Tabs" line doesn't mention the Grantee Leads tab in the Appius file. |
| X4 | Check | The NYSPHA file references an internal Gmail label in Adam's inbox. That's fine for Adam, but it shouldn't go to anyone else as-is. |

### Prospects
| # | Sev | Issue |
|---|---|---|
| X5 | **High** | **The six component columns are 0–1 fractions, but Read Me describes them in points** (mission 30, geography 20…), and only Mission is labelled "(0-1)". For example, Hartford shows Geography 0.50 and Size 0.40, and nothing tells the reader that means 10/20 and 6/15 points. |
| X6 | Medium | Score uses format `0.00`, so a 1-dp score shows a trailing zero (e.g. "xx.x0"). |
| X7 | Medium | `new_grantee_rate` is computed but not exported, so the Openness score can't be checked. `preselected_only` shows only inside the flags string. |
| X8 | Low | 12 non-preselected funders have a blank "How to apply". |

### Validation
| # | Sev | Issue |
|---|---|---|
| X9 | **High — false match** | Appius seed **"Park Foundation"** is reported as `DROPPED: average giving $32,743 under $250,000`. The match is actually **THE SPARK FOUNDATION INC (Natick, MA, EIN 841734642)**: `similarity("park foundation", "spark foundation") = 96.8`, which passes the 95 threshold. The real Park Foundation (Ithaca) isn't in this batch. → **Flag to Workstream #2.** |
| X10 | Note | Every other seed: "not in data yet". This is expected with one month of data, and the Read Me should say so (X2). |

### Dropped
4,829 rows: 4,228 for average giving under $250K and 601 for no NY grants. The reasons are clear. No issues.

### Federal
| # | Sev | Issue |
|---|---|---|
| X11 | Medium | Opens/Closes are text (`11/01/2010`), not dates, so they don't sort chronologically. Closes is blank for 135/188 NYSPHA rows and 95/209 Appius rows. |
| X12 | Medium | There are stale or irrelevant hits: 25 NYSPHA rows opened before 2024 but are still "posted". For example, the row titled "State Veterans Home Construction Grant Program" (opened 2010) was found by the keyword "public health infrastructure", and its Agency column shows a program name, not an agency. Consider filtering by open date or tightening the keywords. |
| X13 | Low | Link is plain text, not a clickable hyperlink. |
| X14 | Medium | If Grants.gov fails, the only notice goes to stderr. The tab then comes out empty and the workbook doesn't say why. |

### Grantee Leads (Appius, INTERNAL)
6 leads. Some theme tags look wrong: an international clean-water charity is tagged `substance_use`, and a housing nonprofit is tagged `rural_health`. Lead names are left out on purpose, because the list is internal and this repo is public. → **Flag to Workstream #3** (taxonomy).

## 3. Tier B/C flag spot-check

| Funder (client, tier, score) | Flags | Do the flags make sense? |
|---|---|---|
| The Shinemaker Foundation (NYSPHA, Tier B) | `new_grantee_rate_assumed` | ✅ The flag is technically right (one year of data), but **every** non-preselected funder has it (116/116), so it tells the reader nothing yet. The funder is in CA with 44% of dollars to NY, and it lands just below Tier A on a single year of data. |
| John A Hartford Foundation (NYSPHA, Tier B) | `new_grantee_rate_assumed, restricts_lobbying` | ❌ **`restricts_lobbying` is a false positive.** It fired on "…a state or **political** subdivision thereof." Also, the median grant is $1,000 on $25.5M of giving, because 29 small $1K gifts dominate the median. That understates its Size component. |
| Evelyn S and K E Barrett Fdn (NYSPHA, C) | `restricts_lobbying` | ⚠️ It fired on "does not make grants to: … **Political campaigns**". Every 501(c)(3) has that restriction, so it says nothing about advocacy/lobbying work. |
| William T Kemper Fdn (NYSPHA, C) | `restricts_lobbying` | ⚠️ It fired on "**politically** partisan purposes". Same issue: the keyword `political` matches all 3 of the 3 flags, and none of them is a real lobbying restriction. |
| Harcourt Jovanovich Fdn (NYSPHA, Tier B) and Marjorie & John Buyers Fdn (NYSPHA, Tier B) | `preselected_only` | ✅ The flag is correct, but **two of six Tier B ("research further") funders don't accept applications.** Openness only costs them ~4 points. Worth raising with whoever owns the model. |
| Alliance for Cancer Gene Therapy (NYSPHA, Tier B) | `new_grantee_rate_assumed, public_charity_schedule_I` | ✅ Correct (Form 990). Note that none of the 51 Schedule I filers in the db has application text (the 990 has no such field), so they can never earn the +0.25 application bonus. |
| Pinkerton, Robinson-Broadhurst, DLM Foundation (NYSPHA, Tier C, each with mission under 0.1) | — | ⚠️ There are no flags, but **73 of 103 NYSPHA B/C funders have mission under 0.3**. This is Known Issue #3 (mission isn't a gate), and it's real in this data. → **Flag to the mission/model owner.** |
| Nassau County AHRC Fdn (Appius, Tier B) | `new_grantee_rate_assumed, public_charity_schedule_I` | ✅ Consistent. |

## Flags for other workstreams (not fixed, per ground rules)
- **#2 Peer/seed:** the Park → Spark false match (X9) is a concrete case where 95 is too loose for short names. Separately, `validate()` hard-codes 95 instead of reading from `model.yaml` (`peer.fuzzy_threshold` is 90).
- **#3 Taxonomy:** an international water charity is tagged `substance_use`, and a housing nonprofit is tagged `rural_health` (names are in the Appius Grantee Leads tab).
- **#3 Taxonomy / model owner:** the `lobbying_keywords` entry `political` causes 3 of 3 false positives, so suggest `"political campaign"` only, or `lobby|legislat`. Also, 73/103 NYSPHA B/C funders have mission < 0.3 (Known Issue #3).
- **#4 Rural:** RUCA coverage is 97.4% of grant dollars, so `rural_data_missing` fires on only 6 funders. Changing the rural cutoff will have a real effect.
- **Model owner:** Activity recency penalises funders whose latest filing in this batch is TY2024 (75 of 478 scored funders). That's an artefact of IRS processing timing.
