# Foundation Prospector

Appius Communications x Cornell Business Analytics team, fall 2026.

Finds the private foundations (and grantmaking public charities such as community
foundations) that fund a client's kind of work in New York, scores each one 0 to 100
against a client profile, and writes a ranked Excel list. Federal opportunities from
Grants.gov are layered on top.

Read this with the **project brief** (Word) and the **kickoff workbook** (Excel). The
workbook's Client Intake, Fit Model and Peer Lists tabs mirror the files in `config/`.

## Be clear on what's done and what isn't

- The code runs end to end, but **only on synthetic test files** in `tests/fixtures/`.
  Every organization, EIN and dollar figure there is made up.
- **It has not touched real IRS data yet.** Expect breakage when it does: element names
  that vary by schema year, odd encodings, very large files. Your first job is proving
  the parser on real filings and fixing what breaks. Parse warnings are logged to the
  `parse_log` table; read them.
- Treat the scoring weights as a hypothesis to test, not an answer.

## Setup

Python 3.10 or newer.

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m pytest -q                # all tests should pass
python -m prospector demo          # end to end on synthetic data, no downloads
```

The demo writes one Excel file per pilot client to `outputs/demo/`. Open them and read
the Read Me tab.

## First steps on real data

Follow "Where to start" in the brief. In commands:

```bash
python scripts/get_reference.py              # IRS BMF (NY + neighbors) and Census ZIP-to-county
#   Download the USDA ERS RUCA ZIP-code file by hand into data/reference/
python -m prospector load-reference
python -m prospector index --year 2025       # how many 990-PFs does the 2025 index list?
python -m prospector download --url https://apps.irs.gov/pub/epostcard/990/xml/2025/<MONTHLY_ZIP_NAME>.zip
python -m prospector ingest data/raw/<MONTHLY_ZIP_NAME>.zip
python -m prospector warnings -n 100         # log every parse warning
python -m prospector match                   # prints the NY match rate (target 60%+)
python -m prospector match-sample --n 50     # hand-check 50 matches
python -m prospector report --client nyspha
python -m prospector report --client appius
```

Monthly zip names change. Check the IRS Form 990 series downloads page for the current
list. The year in the URL is the IRS **processing** year, not the tax year.

## Quarterly refresh (the deliverable Appius runs without you)

```bash
python -m prospector refresh --client nyspha appius --zips data/raw/*.zip
```

One command: ingest any new zips (amended returns replace originals), re-match
recipients, score, and write fresh Excel files. Make sure this works for someone who
has never seen the code before you hand off.

## Adding a new client (no code changes)

Copy `config/clients/nyspha.yaml` to `config/clients/<new_id>.yaml`, fill it in, then
`python -m prospector report --client <new_id>`. If a new client needs a code change,
the model isn't documented well enough yet.

## How it fits together

| Step | Module | What it does |
|---|---|---|
| Ingest | `irs.py`, `parse990.py` | Download the IRS index and monthly zips; parse 990-PF grant lines, application info, the "preselected only" box, and Schedule I for philanthropy-coded (NTEE T) 990 filers in NY and neighbors. Store in SQLite. |
| Enrich | `reference.py`, `match.py` | Load the BMF, Census ZIP-to-county and RUCA files. Match recipients to the BMF by EIN, then exact name, then fuzzy name within the same city. |
| Score | `score.py`, `themes.py` | Hard filters, six components, tiers, flags, validation seeds, grantee leads. Every number comes from `config/model.yaml`. |
| Federal | `grantsgov.py` | Grants.gov Search2 API by keyword and program number (ALN). Cached. |
| Report | `report.py` | One formatted Excel file per client. |

NY State opportunities are not pulled by code. They arrive as SFS Vendor Portal email
alerts in Adam's inbox. A scraper is a stretch goal.

## The fit model in one table

| Component | Points | Notes |
|---|---|---|
| Mission | 30 | Dollar-weighted theme match. Uses in-state grants when there are 3+. Vague "general support" lines with no NTEE code get a neutral 0.25, not zero. |
| Geography | 20 | State 60%, focus region 25%, rural ZIPs 15%. Statewide clients fold region into state. |
| Size | 15 | Median in-state grant vs the ask band (60%); median grantee revenue vs 10x capacity budget (40%). **Not a hard filter.** |
| Peer | 15 | Has it funded anyone on the client's peer list? 1 peer = half, 2+ = full. |
| Openness | 10 | Preselected-only = 0.1. Otherwise 0.5, plus published application process, plus new-grantee rate. |
| Activity | 10 | Giving level, trend, filing recency. |

Tiers: A 70+, B 55 to 69, C 40 to 54, Watch under 40.

## Known issues to work on

These are the real analytics problems (see the brief, "Where the real analytics work is"):

1. **Recipient matching.** 990-PF lines have no recipient EIN. Measure the match rate on
   NY dollars and hand-check accuracy. A wrong match is worse than no match.
2. **Theme keywords are untested.** Hand-label about 200 purpose lines and measure how
   well `config/taxonomy.yaml` does.
3. **A funder with zero mission fit can still reach Tier C.** In the demo, an NYC arts
   funder scores 45 for NYSPHA on geography, size and activity alone. The workbook's
   sandbox expects that kind of funder in Watch. Decide whether mission should act as a
   gate, test it against the validation seeds, and log the decision.
4. **Peer and seed matching are fuzzy.** Seed matching uses a strict 95 threshold so
   "Community Foundation of the Southern Finger Lakes" doesn't match "Finger Lakes
   Community Foundation." Check both on real names.
5. **Schedule I scope.** Only 990 filers coded NTEE T in NY, PA, NJ, CT, MA and VT are
   parsed. If an important community foundation is missing, check its BMF NTEE code.
6. **Rural definition.** RUCA 4 to 10 counts as rural. That isn't HRSA's definition,
   which federal rural health programs use. Pick one and document it.
7. **Filing lag.** The newest tax year is usually partial, which affects the trend and
   recency parts of Activity.

## Working agreements (from the brief)

- Status updates go to Adam: what got done, what's next, what's blocked.
- Don't contact funders, clients, or NYSPHA. Everything goes through Appius.
- **Never commit raw IRS files, the database, or client outputs to git.** `.gitignore`
  covers `data/` and `outputs/`. The Appius grantee lead list is internal.
- Final lists and the documented model go in the shared Google Drive folder
  "Foundation Prospector (Cornell Analytics Team)".
- Scores rank prospects for human review. Check every Tier A funder's current
  guidelines before anyone acts on it.
- Be polite to public servers: cache, space out calls, identify the project in the
  User-Agent (set in `prospector/__init__.py`).
- Log every model change in `docs/MODEL_CHANGELOG.md`.

## Layout

```
config/            model.yaml, taxonomy.yaml, clients/*.yaml
prospector/        the package (python -m prospector ...)
scripts/           get_reference.py
tests/             pytest tests + synthetic fixtures (make_fixtures.py regenerates them)
docs/              MODEL_CHANGELOG.md
data/              downloads and the SQLite database (git-ignored)
outputs/           Excel reports (git-ignored)
```
