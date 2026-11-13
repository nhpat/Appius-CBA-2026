# Labeling guide for grant purpose lines

Each line in `sample.csv` / `holdout.csv` gets a row in `labels.csv` /
`holdout_labels.csv`:

| column | meaning |
|---|---|
| `gold_themes` | Themes the grant really serves, separated by `;`. Blank = none of our themes. |
| `generic_purpose` | `Y` if the purpose text alone is boilerplate that says nothing about mission ("General support", "Charitable", "To aid the donee in its exempt functions"). `N` if it names a field, even an off-theme one ("Religious", "Scholarship", "Medical research"). |
| `note` | Why, when it isn't obvious. |

Judge from the purpose, the recipient name, and the NTEE code, the way a
reviewer at Appius would. Commonly known organizations count (NAMI is mental
health, City Harvest is food rescue), but don't look anything up.

## Theme rules

- **public_health**: prevention and population health; community health
  centers and free clinics; health equity; global health orgs (Partners In
  Health, MSF); healthy-food access *(open decision, see RESULTS.md)*.
  **Not** hospitals, disease-research charities, or medical research.
- **health_workforce**: training, education, or support of health
  professionals: nursing and medical schools *when the purpose says so*,
  residencies, clinical simulation, physician stipends, CHWs.
  **Not** general college scholarships, universities as such, or nursing homes.
- **behavioral_health**: mental health services and advocacy, counseling,
  crisis lines, psychiatry, suicide prevention.
- **substance_use**: addiction prevention, treatment, recovery.
- **rural_health**: health services aimed at rural areas. NTEE can't tell
  this; a hospital is not rural health unless the text says so.
- **agriculture**: farming, farmers, food systems, ag education/extension.
  **Not** animal sanctuaries, schools or camps with "Farm" in the name.
- **human_services**: food banks/pantries, housing, family and youth
  services (Boys & Girls Clubs, Girls Inc), disability and senior services,
  veterans' services, United Ways and Jewish federations.
  **Not** children's hospitals, museums' youth programs, schools.
- **civic_capacity**: advocacy, policy, civil and human rights, coalitions,
  convenings, nonprofit capacity building.

Out of scope (label blank): arts, religion, general education, scholarships,
environment, animals, hospitals, medical research.

Labels were done by one person (an AI assistant, 2026-11-11). **Have a team
member spot-check at least 30 rows**, especially hospitals and food access,
where the rules above are judgment calls.
