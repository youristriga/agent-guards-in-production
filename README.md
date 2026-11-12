# One operator, one agent, real consequences

A field corpus of how an autonomous Claude Code agent fails in daily production, and of what actually stops each failure: a written rule, or a runtime guard.

Since May 2026 a single Claude Code agent runs the day-to-day work of three small businesses in Marseille, France (a bakery and fine-food shop, a B2B food-sourcing service, a studio that builds websites and management tools for drivers, craftsmen and restaurants). It reads the till and the bank accounts, answers clients and suppliers by email, SMS and WhatsApp, prospects, prepares quotes, builds and deploys client websites. One wrong action reaches a real person. One operator, not an engineer by training, supervises it.

Every correction is recorded. Recurring corrections become rules. Rules that keep being broken become **guards**: checks run by Claude Code hooks before a tool call or at the end of a turn, stored as data, able to block. This repository publishes the method, the anonymized aggregate data and a reference implementation of the guard engine.

## The corpus at a glance (November 13, 2026)

| | |
|---|---|
| Error records | **1,929**: 1,250 reported by the operator, 377 self-reported by the agent, 301 logged by a guard, 1 by a client |
| Rules | **497** validated and active, 211 proposed and awaiting the operator, 120 rejected |
| Guards | **46**: 17 enforced (16 block, 1 warns), 1 safety net, 24 in observation, 4 retired |
| Guard engine | loaded in 1,877 sessions; every verdict logged, observation included |
| Replay bench | 40 cases from real incidents, 13 hidden; first run 59 / 120 runs passed on Claude Opus 5.5 |

## What the data already shows

1. **A written rule is not enough.** On the replay bench, with the full rules in context, half the runs still fail on situations a rule covers ([bench](bench/README.md)). Every week since September 21, between 26 % and 49 % of the new errors broke a rule that already existed ([weekly-recurrence.csv](data/weekly-recurrence.csv)).
2. **Guards stop the mechanical failures, not the judgment ones.** In the agent-harness domain, guards caught 188 of 460 errors. In writing (tone, form, wording), the largest category reported by the operator (303), guards caught none and the agent self-reported 16 ([errors-by-domain.csv](data/errors-by-domain.csv)). No guard yet targets writing: a guard can check that a thread was reread before a reply, not yet how the reply reads.
3. **Observation mode is what makes guards safe to add.** A new guard first logs what it *would* have refused. Several were wrong at first (for example a phone-number capture that read an option value as a number) and were fixed from their own logs. [guard-verdicts.csv](data/guard-verdicts.csv) shows how often each guard fires, in observation and enforced.
4. **Hidden cases matter.** Hidden bench cases pass 2 / 13, visible ones 8 / 27: part of the visible success may come from memory written about those very incidents.

## Limits

One operator, one agent, one first bench run on one model (40 cases, three runs each). The replay cases are private, so the bench cannot be rerun from this repository; the case format and a synthetic example are in [bench/](bench/README.md). These limits are what the next step addresses.

## Repository

| Path | What |
|---|---|
| [`METHOD.md`](METHOD.md) | The loop: correction, record, rule, guard, replay. Record formats. How recurrence is measured. |
| [`engine/`](engine/) | Reference guard engine for Claude Code hooks (Python, no dependency), four example guards, tests on synthetic transcripts. |
| [`bench/`](bench/README.md) | How the replay bench isolates a run and judges it, first results, case format. |
| [`data/`](data/) | Aggregate, anonymized data: errors by domain and origin, weekly recurrence, the 46 guards, guard verdict counts, bench results per case. |

Run the engine tests: `python3 -m unittest engine/test_guards.py`

## What is not here, and why

Client names, messages, phone numbers, accounts and the text of individual records are private and stay private. So are the replay cases themselves (they are built from real threads). Rule and guard titles are translated from French and stripped of internal names. Only the method, the aggregates and generic code are published.

## Open questions

1. Which failure types survive a written rule and only stop with a runtime guard, and which survive both?
2. Do newer models need fewer of these rules? The same replay cases on several models, several runs each, would say which rules a model has made unnecessary.
3. How well does a cheap pre-filter catch prompt injection hidden in inbound third-party messages (email, SMS, call transcripts) before the agent reads them? A first filter is in production; it has not yet been measured against several models on a fixed set.

## Author

Youri Striga, Marseille. Operator of the three businesses and of the agent. The code in this repository was written with Claude Code.

Code under the MIT license, data under CC BY 4.0 (see [`LICENSE`](LICENSE)).
