# Workstream 5 (Reporting / QA): plain-English summary

The full evidence is in [FINDINGS.md](FINDINGS.md). This page explains it for someone who hasn't seen the code.

## What the tool does
Foundations file an IRS tax form every year that lists every grant they gave. The tool reads those forms and scores each foundation from 0 to 100 on how well it fits a client (NYSPHA or Appius). It then writes a ranked Excel spreadsheet: Tier A means pursue now, B means research further, C means keep on file, and Watch is a long shot.

## What this workstream checked
Two things: that the spreadsheets are correct and readable, and that someone who has never seen the code can run the quarterly update command.

## What was done
1. **Set up from scratch.** I made a fresh copy of the code, loaded the team's shared database and ran the tests. All 27 tests passed, and the match rate was 61% as expected.
2. **Generated both spreadsheets** and reviewed every tab, not just the ranked list.
3. **Spot-checked the warning labels** ("flags") on Tier B and C foundations against the underlying data.
4. **Tested the update command** in five ways:
   - as documented in zsh (the macOS default shell)
   - as documented in bash
   - without new data files
   - with a new data file, including loading the same file twice
   - with no database at all

## What was found
**The update command**
- As written in the README, it crashes, because it looks for a `data/raw/` folder that nobody on the shared-database setup has. On Windows it can't work at all.
- With the database missing, it fails silently. It produces a junk spreadsheet, including a fake top-tier foundation, with no error message. It also overwrites that day's real report.
- Run without `--zips`, it works and takes a few seconds.

**The spreadsheets**
- None of the nine warning labels is explained anywhere in the file.
- The score columns show decimals (e.g. 0.75), while the instructions describe scores in points (e.g. "out of 20").
- Nothing warns that the data covers only one month of IRS filings. That's why there are no Tier A foundations and most known-good foundations aren't found yet.

**Errors in the results**
- **The lobbying label was wrong all 3 times it appeared.** It triggers on any use of the word "political", including "political subdivision" (a government body) and "no political campaigns" (a rule every charity follows).
- **One check foundation was matched to the wrong organization.** "Park Foundation", which is on the known-good list used to sanity-check the tool, was matched to "Spark Foundation", a different organization in Massachusetts, because the names are nearly identical.
- **Many middle-tier foundations barely fit the client's mission.** 73 of the 103 NYSPHA Tier B/C foundations have a weak mission match. They rank well on size and location instead.

## What happens next
- **Code owners:** handle the data-file pattern inside Python, refuse to run on an empty database, and document that the handoff depends on the shared database.
- **Report owner:** add a flag legend, label score columns consistently, and add a data-coverage note to the Read Me tab.
- **Passed to other workstreams:**
  - name matching (#2): the Park/Spark mix-up
  - theme keywords (#3): wrong theme tags
  - model owner: the lobbying keyword and the mission-gate question
- No model settings were changed.

The spreadsheets themselves are in the team's shared Google Drive folder, not in this repo, because outputs are never committed and the repo is public.
