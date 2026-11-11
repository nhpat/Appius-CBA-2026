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
| 2026-11-11 | Theme Taxonomy | **Matching rules** (`themes.py`): punctuation-insensitive; keywords match at word start (quoted trailing space = whole word); per-theme `exclude` phrases; new `generic_exact` list | Substring matching tagged Sudbury/South Sudan as substance use (YAML had silently dropped the space in `sud `), "Branches" as agriculture (`ranch`), "Nursery" as workforce | Seeds not in data yet (1 month ingested). Holdout micro precision 0.32→0.76, recall 0.40→0.65 (all changes together). See `analysis/taxonomy_eval/` |
| 2026-11-11 | Theme Taxonomy | health_workforce: dropped `scholarship`, bare `workforce`, `fellowship`, `residency`, `pipeline`, `training program`, `nurse`/`nursing`, and NTEE E30/B42/B43/J. Added specific health-profession phrases | 3% precision on 240 labeled lines. Colleges, scholarships = 8% of NY-area dollars falsely tagged | NYSPHA: scholarship funders lose up to 21 pts (Leopold Schepp B→Watch) |
| 2026-11-11 | Theme Taxonomy | rural_health: dropped NTEE E21/E22/E32 and bare `rural`; added telehealth/rural clinic phrases | Every hospital was tagged rural health (0 of 7 tags correct) | NYSPHA: hospital-heavy funders lose rural credit |
| 2026-11-11 | Theme Taxonomy | public_health: dropped NTEE G, H; added E32 and community health center / clinic / global health / healthy food / nutrition keywords | G/H tags were disease-research charities (0 of 4 correct); health centers were missed | UNFI Foundation Watch→B for NYSPHA via food access. **Open decision**: is food access public health? |
| 2026-11-11 | Theme Taxonomy | agriculture NTEE K→K2 (food programs K3/K4 moved to human_services); `farm` whole-word with `farm animal` excluded; dropped `ranch`, `mediation program` | Food banks were tagged agriculture; animal sanctuaries and schools named "Farms" too | Small |
| 2026-11-11 | Theme Taxonomy | human_services: added NTEE O, K3, K4, I7 (dropped rest of I); food bank/shelf, soup kitchen, needy, disability, veteran, United Way, federation keywords; excluded children's hospitals/museums | Recall was 0.18 on holdout; Boys & Girls Clubs, food banks missed; Everytown (I20) mis-tagged | Appius: B 2→3 |
| 2026-11-11 | Theme Taxonomy | civic_capacity: dropped `association`; added civil/human rights, ACLU, social justice. behavioral_health: added mental illness, psycholog; excluded credit counseling, crisis relief. substance_use: `recovery` → specific recovery phrases; added drug abuse/awareness/free/prevention, sober | `association` = 134 lines of symphonies and alumni groups; "recovery" hit a soup kitchen and arts orgs' financial recovery | Small |
| 2026-11-11 | Theme Taxonomy | generic_purpose: added general fund/use/contribution/donation/grant, operating fund/budget, charity, exempt function/purpose/organization, program services, see statement/attached/schedule; `generic_exact`: general, donation, operations, support, gift, grant | 20 of 61 boilerplate lines (no NTEE) were scored 0 instead of the neutral 0.25 | NY-area dollars scored vague 13%→20%; vague-flagged funders 30→52 |
| | | | | |
