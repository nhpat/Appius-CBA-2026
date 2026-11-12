# Task 2 · Peer and seed matching

The threshold of **95 misses verified aliases**. Retain it provisionally for automatic seed matching, add verified aliases or EINs for known identities, and use **89 as a human review trigger** for close names. A lower automatic cutoff introduces false matches in this sample. Peer matching currently uses **90** in `config/model.yaml`, while seed validation defaults to **95** in `prospector/score.py`.

The evaluation extracts 33 configured entries representing 31 unique names. It compares normalized names using the production `similarity()` function and RapidFuzz 3.14.6. The measured sample contains 14 documented alias pairs and 26 distinct organization pairs. Sources accompany each pair in `evaluate.py` and the generated CSV. Formatting controls and the repository's Finger Lakes guardrail are excluded from these metrics.

| Cutoff | Aliases caught out of 14 | False matches out of 26 |
|---:|---:|---:|
| 75 | 5 | 2 |
| 80 | 5 | 1 |
| 89 | 3 | 1 |
| 90 | 1 | 1 |
| 95 | 1 | 0 |
| 100 | 0 | 0 |

New York Health Foundation and its former name, New York State Health Foundation, score **89.66**. The Health Foundation for Western and Central New York and its former Community Health Foundation name score **89.36**. Both fail at 95. These organizations document their name changes. [New York Health Foundation announcement](https://nyhealthfoundation.org/2022/05/17/an-updated-name-the-same-commitment/) · [Health Foundation history](https://hfwcny.org/about/our-story/)

Common Ground Health and Finger Lakes Health Systems Agency score **40.74** despite their documented DBA relationship. The Tower Foundation's full configured name and its published Peter & Elizabeth Tower Foundation variant score **96.97** and pass at 95. [Common Ground Health identity](https://commongroundhealth.org/privacy-policy) · [Tower Foundation annual report](https://thetowerfoundation.org/app/uploads/2020/08/TF20001_2019_Annual_Highlights_Digital_V2-Final.pdf)

Connecticut Public Health Association and Connecticut Association of Health Plans are different organizations, yet score **90.41**. This pair passes the current peer cutoff and also passes at 89. A false peer match can add 7.5 points to a funder's score. The matching name would need to occur in that funder's grants for an actual award. [Public health association](https://cpha.info/) · [Health plans association](https://www.ctahp.com/aboutus.htm)

The required Community Foundation of the Southern Finger Lakes / Finger Lakes Community Foundation example scores **88.00** and is rejected at 95. Its expected rejection comes from the repository. Independent evidence establishing two legal entities for this exact pair remains unresolved.

The sample deliberately includes difficult aliases and a negative discovered during database inspection. Its error rates are exploratory. Documented aliases cover **13 of 31 names**, leaving **18 names** with formatting controls and unverified database candidates. More identity research and an independent evaluation set are needed before selecting a production cutoff. Normalization can also erase distinctions, as in the constructed names `Example Trust` and `Example Fund`, which score 100.

Reproduce the comparison from the repository root with `.venv/bin/python docs/peer_seed_review/evaluate.py`. Results appear under `outputs/peer_seed_review/`, including the inventory, labeled comparisons, threshold metrics and JSON summary. With the shared database installed, the evaluator also generates nearest name candidates through a read only connection.
