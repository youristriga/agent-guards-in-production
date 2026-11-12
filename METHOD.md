# Method

## The loop

```
operator correction ──► error record ──► rule (proposed) ──► rule (validated by the operator)
        ▲                                                          │
        │                          broken again                    ▼
   replay bench ◄──── guard (observation ──► enforced) ◄──── error linked "violated"
```

1. **Correction.** When the operator corrects the agent ("you sent that without reading her last message"), the agent records it in the same turn: the operator's exact words, what happened, the cause, the control that would have caught it, the domain (email, SMS, banking, websites...). A guard checks this: a turn that contains a correction and ends without a record is flagged.
2. **Other sources.** The agent also records its own mistakes when it notices them, and every guard refusal is recorded as an error with origin `guard`.
3. **Rule.** A new error is compared with existing records. When the same failure comes back, it becomes a proposed rule: a trigger ("before replying on an existing thread") and a gesture ("reread the whole thread, both directions"). The operator validates or rejects it. Validated rules are injected into the agent's context: the core ones in the instruction file read every turn, the others at session start, and the full text of any rule on demand.
4. **Link.** Each error is linked to rules: `produced` (the error gave birth to the rule), `violated` (a rule existed and was broken), `reinforced`.
5. **Guard.** A rule that keeps being violated is a candidate for a guard. A weekly job proposes, for each rule broken repeatedly, one of: write a guard, rewrite the gesture, or archive the rule. The operator decides.
6. **Observation first.** A new guard runs in observation: it logs what it would have refused, never blocks. Its log is read; false refusals are fixed; then it is switched to enforced. A guard is changed by depositing a new version of its record, never by editing code.
7. **Replay.** Real incidents become bench cases (see [bench/](bench/README.md)), so that a change of rules, guards or model can be measured on the situations that actually went wrong.

## Records

**Error** (1,929): date, short subject, domain, origin (`operator`, `agent`, `guard`, `client`), the operator's words verbatim, the fact, the cause, the control, state (open / closed), closed by what proof.

**Rule** (856 in total): number (for the 70 or so core rules), title, statement, the incident that produced it, the control, the gesture, the intentions it applies to (the operator's own phrasings, used to retrieve the rule at the right moment), domain, validation (`validated`, `to validate`, `rejected`), state (`active`, `replaced`, `archived`).

**Guard** (46): name, version, state, effect (`block` or `warn`), moment (`before tool call` or `end of turn`), the rule it enforces, the message the agent receives, why it exists, what its measurements showed, and the spec in a small declarative grammar (trigger, exemptions, captured values, what must have happened before). The grammar is the one implemented in [`engine/guards.py`](engine/guards.py). The production engine adds a few constructs (time windows, lookups that translate a captured value through a service before comparing it).

**Verdict**: guard, version, session, sub-agent type, moment, tool, verdict (`blocked`, `warned`, `would have blocked`, `would have warned`, `lifted by operator`), extract.

## Measuring recurrence

For each week, among the new error records:

- `repeat_of_existing_rule`: errors linked `violated` to a rule validated before the error;
- `repeat_blocked_by_guard`: of those, the ones a guard stopped before they reached anyone;
- `repeat_reached_operator`: the others.

`share_repeat` is the first divided by all errors of the week. A rule that works should drive its own repeats to zero; a guard turns repeats that reach the operator into repeats that are blocked.

Caveats, stated plainly:

- Recording became systematic in the second half of September (agent self-reports, guard refusals logged as errors). Earlier weeks are undercounted, and the jump in volume that week is a change of recording, not a change of behavior.
- 300 records have no domain.
- "Reported by the operator" includes corrections the operator made by voice or in passing and that the agent recorded; their wording is the operator's, their classification is the agent's.
- One operator, one agent, one set of businesses. Nothing here is a controlled experiment. The replay bench is the controlled part.

## Inbound injection pre-filter

Every inbound third-party text (email, SMS, WhatsApp, call transcripts, social messages) passes through a pre-filter before an agent can read it raw: a model judges whether it carries instructions aimed at an AI; a suspect text is withheld from the agent, which receives an alert and a summary instead. A dedicated read-only sub-agent reads third-party content when the main session does not need it verbatim, and returns fields (who, what is asked, amount, date), never the text. Measured so far: on a sample of real inbound mail, the first version held back ordinary messages because they carried a link (a signature, a newsletter); the instruction and a second-reading step were rewritten and re-measured. The open question is a proper benchmark across models.
