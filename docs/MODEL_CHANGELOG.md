# Model change log

Every change to `config/model.yaml`, `config/taxonomy.yaml` or a client profile goes
here: what changed, why, and what it did to the validation seeds. This record is what
makes the model "documented."

| Date | Who | Change | Why | Effect on validation seeds |
|---|---|---|---|---|
| 2026-09-24 | Adam | Ask band $50K to $500K for both clients; capacity budget added | Appius manages the grants, so targets sit above the clients' own size | Not yet run on real data |
| 2026-09-24 | Adam | Minimum average annual giving raised from $50K to $250K | A smaller funder can't realistically make a $50K+ grant | Not yet run on real data |
| 2026-09-24 | Adam | Size is not a hard filter | Big funders stay on the list and score lower on size | Not yet run on real data |
| 2026-09-24 | Adam | Appius focus: WNY + Finger Lakes full region credit, rest of upstate half | Where Appius works | Not yet run on real data |
| | | | | |

## 2026-11-11 — Rural Definition Validation (Known Issue #6)

**Setting:** `geography.rural_ruca_min: 4`  
**Decision:** Retain the current RUCA 4–10 threshold. No production model changes.

### Rationale

Compared the existing rural classification against HRSA's FY2026 ZIP Code Approximations dataset. HRSA incorporates county and census-tract criteria beyond the current RUCA cutoff, making the existing approach an approximation rather than an official HRSA determination.

The analysis found that 3,057 of 41,150 project ZIP codes changed rural status, with a net $10,465,944 increase in rural-classified grant dollars.

### Impact on Client Scores

- **NYSPHA:** 478 prospects; 45 geography scores changed, 38 displayed total scores changed, 135 rankings changed, and 0 tier changes.
- **Appius:** 478 prospects; 46 geography scores changed, 37 displayed total scores changed, 166 rankings changed, and 1 tier change.

Example: Jack O McCall Sr and Dolores L McCall Foundation increased from 38.9 to 40.6 for Appius, moving from Watch to Tier C under the simulated HRSA classification.

### Decision and Next Steps

Retain RUCA 4–10 for the current handoff because it provides a consistent, reproducible geographic indicator and HRSA adoption requires more than a threshold adjustment.

Recommend integrating HRSA's published ZIP approximation as a separate, configurable measure in a future model update, particularly where federal rural-health alignment is relevant.

**Validation limitations:** Limited IRS filing sample; 120 ZIP records with incomplete classification comparison; 719 grants lacking matching project ZIP geography. The HRSA scoring simulation also treats ZIPs without HRSA classifications as missing.

**Configuration changed:** None.  
**Production score impact:** None.  
**Validation seed impact:** Not separately measured; no seed scores change in the unchanged production model.