# Data

Aggregates only, extracted on November 13, 2026 (bench: run of October 5, 2026). No record text, no names.

| File | Rows | Content |
|---|---|---|
| `errors-by-domain.csv` | 21 | Error records by domain and by who reported them (operator, agent itself, guard). The one record reported by a client is not in a column. Column totals: 1,250 / 377 / 301, 1,928 in all. |
| `weekly-recurrence.csv` | 20 | Per week (Monday): errors, errors that broke an existing rule, of which blocked by a guard or reaching the operator, and the origin split. The last week was in progress at extraction. |
| `guards.csv` | 46 | Every guard: name, state (enforced, observation, safety net, retired), effect (block, warn), when it is checked, the rule it enforces (translated). |
| `guard-verdicts.csv` | 44 | Verdict counts per guard since the engine was introduced (October 4, 2026), with the number of distinct sessions. |
| `bench-2026-10-05.csv` | 40 | Replay bench: per case, family, rule numbers, hidden or not, negative case or not, runs passed out of three. Case names replaced by numbers. |
