#!/usr/bin/env python3
"""Guards as data: a reference engine for Claude Code hooks.

The engine knows nothing about any particular guard. Each guard is a JSON record
(see examples/guards.json): when it fires, what it requires to have happened
earlier in the turn or the conversation, and what to do if that is missing.
Adding or changing a guard is a data change, never a code change.

Wire it as a PreToolUse hook and as a Stop hook:

    {"hooks": {
      "PreToolUse": [{"matcher": "*", "hooks": [{"type": "command",
          "command": "python3 /path/engine/guards.py --guards /path/guards.json"}]}],
      "Stop": [{"hooks": [{"type": "command",
          "command": "python3 /path/engine/guards.py --guards /path/guards.json"}]}]}}

Guard states:
  enforced     blocks (or warns) for real
  observation  never blocks; logs what it would have done to --log (JSONL)
  retired      ignored

Grammar of a guard (all regexes are Python, case-insensitive):
  name, state, effect: block|warn, moment: before_tool|end_of_turn, message
  trigger:  {tool, command, path, final_text}   what makes the guard look
  unless:   [pattern, ...]                       a call in the turn that exempts it
  captures: [{regex with (?P<v>...), normalize}] values taken from the triggering call
  require:  {any_of: [pattern, ...], when: before|after|anywhere, scope: turn|conversation,
             link: each_capture|none}
The transcript is written asynchronously and may lag behind the last tool call;
at the end of a turn a check run in the last instant can be missed (false block).
A Stop guard with effect "warn" produces no output: only blocks act at end of turn.

A pattern matches one tool call: {tool, command, path, capture, normalize}.
With link=each_capture, every captured value must appear in some earlier call
matching `require` (e.g. every recipient of a message must have had its thread reread).
"""
import argparse
import json
import re
import sys
import time

FLAGS = re.I | re.S


def normalize(value, how):
    if how == 'lower':
        return value.lower()
    if how == 'digits9':  # phone numbers: compare the last nine digits
        d = re.sub(r'\D', '', value)
        return d[-9:] if len(d) >= 9 else None
    return value


def call_text(call, field):
    inp = call.get('input') or {}
    if field == 'command':
        return str(inp.get('command', ''))
    if field == 'path':
        return str(inp.get('file_path') or inp.get('path') or inp.get('url') or '')
    return json.dumps(inp, ensure_ascii=False)


def matches(pattern, call):
    if 'tool' in pattern and not re.search(pattern['tool'], call.get('tool', ''), FLAGS):
        return False
    for field in ('command', 'path'):
        if field in pattern and not re.search(pattern[field], call_text(call, field), FLAGS):
            return False
    return True


def captured(spec, call):
    text = call_text(call, spec.get('on', 'command'))
    out = set()
    for m in re.finditer(spec['regex'], text, FLAGS):
        v = normalize(m.group('v'), spec.get('normalize'))
        if v and not (spec.get('exclude') and re.search(spec['exclude'], v, FLAGS)):
            out.add(v)
    return out


def read_transcript(path):
    """Tool calls of the whole conversation, the index where the current turn starts,
    and the text of the last assistant message."""
    calls, turn_start, final = [], 0, ''
    try:
        lines = open(path, encoding='utf-8').read().splitlines()
    except (OSError, TypeError):
        return calls, turn_start, final
    for raw in lines:
        try:
            entry = json.loads(raw)
        except ValueError:
            continue
        msg = entry.get('message') or {}
        content = msg.get('content')
        if entry.get('type') == 'user':
            # A real prompt (not a tool result, not an injected reminder) opens a new turn.
            if isinstance(content, str) and not content.lstrip().startswith('<'):
                turn_start = len(calls)
            elif isinstance(content, list) and any(c.get('type') == 'text' for c in content) \
                    and not any(c.get('type') == 'tool_result' for c in content):
                turn_start = len(calls)
        elif entry.get('type') == 'assistant' and isinstance(content, list):
            for c in content:
                if c.get('type') == 'tool_use':
                    calls.append({'tool': c.get('name', ''), 'input': c.get('input') or {}})
                elif c.get('type') == 'text' and c.get('text', '').strip():
                    final = c['text']
    return calls, turn_start, final


def judge(guard, calls, turn_start, current=None, final=''):
    """Return None when the guard passes, else the reason it fires."""
    trig = guard.get('trigger', {})
    if guard['moment'] == 'before_tool':
        if current is None or not matches(trig, current):
            return None
        subject = current
    else:
        subject = None
        if 'final_text' in trig:
            if not re.search(trig['final_text'], final or '', FLAGS):
                return None
        if any(k in trig for k in ('tool', 'command', 'path')):
            hits = [c for c in calls[turn_start:] if matches(trig, c)]
            if not hits:
                return None
            subject = hits[-1]
    turn = calls[turn_start:]
    # Before a tool call, an exemption applies to that call only (a --help earlier in the
    # turn must not exempt every later send). At the end of a turn, to any call of the turn.
    scope_unless = [subject] if guard['moment'] == 'before_tool' else turn
    if any(matches(p, c) for p in guard.get('unless', []) for c in scope_unless):
        return None
    req = guard.get('require')
    if not req:
        return guard['message']
    pool = turn if req.get('scope', 'turn') == 'turn' else calls
    if subject is not None and subject in pool:
        i = len(pool) - 1 - pool[::-1].index(subject)
        if req.get('when', 'before') == 'before':
            pool = pool[:i]
        elif req['when'] == 'after':
            pool = pool[i + 1:]
    found = [c for c in pool if any(matches(p, c) for p in req['any_of'])]
    if req.get('link') == 'each_capture' and subject is not None:
        wanted = set()
        for spec in guard.get('captures', []):
            wanted |= captured(spec, subject)
        seen = set()
        for c in found:
            for p in req['any_of']:
                if matches(p, c) and 'capture' in p:
                    seen |= captured({'regex': p['capture'], 'normalize': p.get('normalize'),
                                      'on': p.get('on', 'command')}, c)
        if not wanted:  # nothing captured: the call cannot be checked, so it is not let through
            return guard['message'].replace('{missing}', '(no value captured from the call)')
        missing = sorted(wanted - seen)
        return guard['message'].replace('{missing}', ', '.join(missing)) if missing else None
    return None if found else guard['message']


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--guards', required=True)
    ap.add_argument('--log', default=None, help='JSONL file for every verdict (observation included)')
    args = ap.parse_args()
    event = json.load(sys.stdin)
    guards = [g for g in json.load(open(args.guards)) if g.get('state') != 'retired']
    calls, turn_start, final = read_transcript(event.get('transcript_path'))
    hook = event.get('hook_event_name')
    current = None
    if hook == 'PreToolUse':
        moment = 'before_tool'
        current = {'tool': event.get('tool_name', ''), 'input': event.get('tool_input') or {}}
    elif hook == 'Stop':
        moment = 'end_of_turn'
        if event.get('stop_hook_active'):
            return 0  # never loop: a turn already sent back by a guard is let through
    else:
        return 0
    blocks, warns = [], []
    for g in (g for g in guards if g['moment'] == moment):
        reason = judge(g, calls, turn_start, current, final)
        if reason is None:
            continue
        observed = g.get('state') == 'observation'
        if args.log:
            with open(args.log, 'a', encoding='utf-8') as f:
                f.write(json.dumps({'at': time.time(), 'guard': g['name'], 'effect': g['effect'],
                                    'observation': observed, 'session': event.get('session_id'),
                                    'reason': reason}, ensure_ascii=False) + '\n')
        if observed:
            continue
        (blocks if g['effect'] == 'block' else warns).append(f"[guard {g['name']}] {reason}")
    if moment == 'before_tool':
        if blocks:
            print(json.dumps({'hookSpecificOutput': {'hookEventName': 'PreToolUse',
                                                     'permissionDecision': 'deny',
                                                     'permissionDecisionReason': '\n'.join(blocks + warns)}}))
        elif warns:
            print(json.dumps({'hookSpecificOutput': {'hookEventName': 'PreToolUse',
                                                     'additionalContext': '\n'.join(warns)}}))
    elif blocks:
        print(json.dumps({'decision': 'block', 'reason': '\n'.join(blocks + warns)}))
    return 0


if __name__ == '__main__':
    sys.exit(main())
