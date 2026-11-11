# Theme taxonomy evaluation (Known Issue #2)

Mission fit is 30 of 100 points and depends entirely on `config/taxonomy.yaml`.
This folder measures how well it tags real grant text, records what was
changed, and lets anyone re-run the check.

**Data:** IRS 2025 processing-year zip `2025_TEOS_XML_01A` (2,328 filings,
22,348 grant lines), recipients matched to the BMF for NTEE codes (NY dollar
match rate 54%). One month of data; re-run on the full year when it's ingested.

## Method

1. `sample_lines.py` draws grant lines to NY + neighbor states (at most 2 per
   funder):
   - **Main set, 240 lines**: 140 simple random, 60 enriched with health/food/youth
     words, and 40 targeted at the sparse client themes (substance use,
     agriculture, workforce). The revision was tuned on this set.
   - **Holdout, 100 lines**: 70 random + 30 targeted, drawn fresh and **labeled
     before the revised taxonomy was run on them**. Use these numbers.
2. Each line is hand-labeled per `LABELING.md` (`labels.csv`, `holdout_labels.csv`).
3. `eval_themes.py` runs `ThemeTagger.tag()` / `is_vague()` exactly as
   `score.py` does and reports per-theme precision and recall, every wrong and
   missed tag with the rule that fired, the `is_vague()` checks, and (`--audit`)
   which rules drive each theme's dollars across the whole DB.
4. `compare_scores.py` scores both pilot clients under the old and new taxonomy.

```bash
python analysis/taxonomy_eval/eval_themes.py --set holdout          # current taxonomy
python analysis/taxonomy_eval/eval_themes.py --set holdout --taxonomy analysis/taxonomy_eval/taxonomy_v0.yaml
python analysis/taxonomy_eval/eval_themes.py --set all --audit
python analysis/taxonomy_eval/compare_scores.py
```

Saved outputs: `results_v{0,1}_{main,holdout}.txt`, `audit_v{0,1}.txt`,
`score_compare.txt`. `taxonomy_v0.yaml` is the original taxonomy.

## Results: per-theme precision / recall

**Holdout (100 lines, not used for tuning)**

| theme | gold | v0 precision | v0 recall | v1 precision | v1 recall |
|---|---:|---:|---:|---:|---:|
| public_health | 6 | 0.40 | 0.33 | 0.75 | 0.50 |
| health_workforce | 2 | **0.07** | 0.50 | 1.00 | 1.00 |
| behavioral_health | 4 | 1.00 | 0.75 | 1.00 | 1.00 |
| substance_use | 3 | 0.60 | 1.00 | 1.00 | 1.00 |
| rural_health | 0 | **0.00** (4 FP) | – | – (0 FP) | – |
| agriculture | 1 | 0.17 | 1.00 | 0.33 | 1.00 |
| human_services | 22 | 0.57 | **0.18** | 0.80 | 0.55 |
| civic_capacity | 5 | 0.33 | 0.60 | 0.50 | 0.60 |
| **all themes (micro)** | 43 | **0.32** | **0.40** | **0.76** | **0.65** |

Lines whose whole predicted theme set was right: 47/100 → 80/100.

**Main set (240 lines; v1 tuned on these, so v1 is optimistic)**: micro
precision 0.35 → 0.77, recall 0.48 → 0.74; exact-set lines 139 → 199.
Per theme: see `results_v*_main.txt`.

Small counts: several themes have under 10 gold lines, so their numbers are
rough. `rural_health` had **zero** true positives in 340 lines; in this data
nearly every "rural health" tag was a hospital.

## What was wrong (v0)

Wrong tags, by rule, on the main set (77 false positives in total):

| rule | wrong tags | what it caught |
|---|---:|---|
| `health_workforce` kw `scholarship` | 17 | every college scholarship. 712 lines / $7.3M across the DB |
| `human_services` kw `child` | 10 | children's hospitals, a deaf school, arts programs for children |
| `human_services` kw `youth` | 6 | museum youth programs, "scholarships to Lexington youths" |
| `agriculture` kw `farm` | 6 | farm-animal sanctuaries, Avon Old **Farms** School, Farm & Wilderness camps |
| `health_workforce` NTEE B42/B43 | 5 | **every college/university grant**: $14.3M, the biggest single source of workforce dollars |
| `rural_health` NTEE E21/E22/E32 | 6 | every hospital (NY-Presbyterian $3.5M, BIDMC, Hartford Hospital…) |
| `agriculture` NTEE K30 | 5 | food banks/City Harvest (they're human services) |
| `public_health` NTEE G/H | 4 | disease-research charities (FSHD, autism, cancer support) |
| `civic_capacity` kw `association` | 2 | symphony and nursery "associations": 134 lines across the DB |
| `health_workforce` NTEE E30, J | 3 | clinics, a family-services org |
| `health_workforce` kw `nurse`/`nursing`, `training program`, `workforce` | 5 | Day **Nurse**ry, nursing homes, I/DD vocational training, a county workforce board |
| `substance_use` kw `recovery` | 1 | Columbia County **Recovery Kitchen** (soup kitchen) |
| `rural_health` kw `rural` | 1 | Tioga County Rural Ministry |

Matching bugs found in the full DB (not just the sample):
- **`sud ` lost its space.** YAML drops an unquoted trailing space, so the
  keyword became `sud` and tagged Sudbury Valley Trustees, Sudbury Food Pantry,
  and "schools in South Sudan" as substance use.
- **`ranch` matched inside `branch`**: a $500K Red Cross "chapters and
  branches" grant was tagged agriculture.
- `nurse` matched "nursery"; `farm` matches "Farmington".

Missed tags (v0), main patterns:
- **Youth development (NTEE O)** wasn't mapped: Boys & Girls Clubs, Girls Inc.
- Food banks named "Food Bank", "Food Shelf", "Soup Kitchen" (only "food pantry" was a keyword).
- Community health centers coded E30/E32 went to workforce/rural, not public health.
- NAMI ("mental **illness**"), "Drug Awareness Council", civil-rights orgs (ACLU), federations.

### `is_vague()` in both directions

| check | v0 main | v1 main | v0 holdout | v1 holdout |
|---|---:|---:|---:|---:|
| (a) boilerplate purpose + no real theme, but got a theme tag | 25/103 | 3/103 | 10/34 | 2/34 |
| (b) boilerplate purpose, no theme, no NTEE → correctly vague (0.25) | 41/61 | 56/61 | 13/18 | 17/18 |
| (c) real-theme line wrongly fell through as vague | 6/83 | 8/83 | 7/42 | 5/42 |
| (d) specific purpose wrongly judged vague | 0 | 0 | 0 | 0 |

(a) is the "General support should not pick up a theme" check. In v0 those
tags came almost entirely from NTEE and recipient-name rules (universities →
workforce, hospitals → rural, "Children's Hospital" → human services). (b)
was failing because common boilerplate was missing from the list: "General",
"General fund", "Donation", "Operations", "General use", "Exempt functions",
"See statement". (c) is the hard residue. These lines have generic purposes,
and only knowing the org tells you the theme (Salvation Army, Doctors Without
Borders, CityHarvest with no BMF match). Better recipient matching (Known Issue
#1) gives them an NTEE code, which fixes them.

## What changed

**`prospector/themes.py`**: matching rules (documented at the top of
`taxonomy.yaml`, tested in `tests/test_themes.py`):
- punctuation-insensitive (`Boys & Girls` = `boys girls`);
- keywords match at the **start of a word** (`ranch` ≠ `branch`), and a quoted
  trailing space means whole word (`"sud "`);
- optional per-theme `exclude` phrases (e.g. `children's hospital` for `child`);
- new `generic_exact` list: purposes that are vague only when they're the whole text ("General", "Donation").

**`config/taxonomy.yaml`**: full diff in git; summary in `docs/MODEL_CHANGELOG.md`.

**Effect on scores** (`score_compare.txt`, this one month of data):
- NYSPHA: B 6→4, C 36→24, Watch 123→137. 15 funders C→Watch. The biggest
  drops (−21) are scholarship funders that got full workforce credit
  (e.g. Leopold Schepp Foundation, previously **Tier B**).
- Appius: B 2→3, C 25→23; small changes.
- Share of NY-area dollars scored vague (0.25): 13.4% → 20.4%.
- Validation seeds: none are in this one-month sample yet, so the seed effect is **not yet measured**.

## Open decisions for the team

1. **Is healthy-food access public health?** I labeled it public_health +
   human_services. With that, UNFI Foundation (grocery distributor, food-access
   grants) jumps Watch → **B** for NYSPHA (29.5 → 59.5). If Adam wouldn't pitch
   UNFI to NYSPHA, remove `healthy food` and `nutrition` from public_health.
2. **Hospitals and medical research** are labeled "no theme". That's
   defensible for NYSPHA, but it's a policy choice. Consider a separate
   `health_care` theme with a low weight.
3. **`youth` / `child`** still cause most of the remaining wrong tags (arts and
   museum youth programs). Options: require service words ("youth services",
   "child welfare"), or accept them since human_services carries no weight for NYSPHA.
4. **rural_health has no working signal.** Text rarely says "rural". Consider
   dropping the theme and letting Geography's RUCA rural share carry it, or
   tagging health lines whose recipient ZIP is rural.
5. **Long boilerplate over 60 chars** ("To aid the donee organization in carrying
   out its exempt functions", 121 lines) is still not vague because of the
   60-character cap in `is_vague()`. Raise the cap or exempt known phrases.
6. Candidate (seen only in the holdout, so not applied to avoid tuning on it):
   map NTEE **E50** (rehabilitative/disability care: Easter Seals, therapeutic
   riding) to human_services.
