"""Tests of the reference engine on synthetic transcripts: python3 -m unittest engine/test_guards.py"""
import json
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
GUARDS = os.path.join(HERE, 'examples', 'guards.json')


def transcript(*turns):
    """turns: (prompt, [bash commands], final text)"""
    lines = []
    for prompt, commands, final in turns:
        lines.append({'type': 'user', 'message': {'role': 'user', 'content': prompt}})
        for i, cmd in enumerate(commands):
            lines.append({'type': 'assistant', 'message': {'content': [
                {'type': 'tool_use', 'id': f't{i}', 'name': 'Bash', 'input': {'command': cmd}}]}})
            lines.append({'type': 'user', 'message': {'content': [
                {'type': 'tool_result', 'tool_use_id': f't{i}', 'content': 'ok'}]}})
        if final:
            lines.append({'type': 'assistant', 'message': {'content': [{'type': 'text', 'text': final}]}})
    f = tempfile.NamedTemporaryFile('w', suffix='.jsonl', delete=False)
    f.write('\n'.join(json.dumps(l) for l in lines))
    f.close()
    return f.name


def run(event, log=None):
    args = [sys.executable, os.path.join(HERE, 'guards.py'), '--guards', GUARDS]
    if log:
        args += ['--log', log]
    out = subprocess.run(args, input=json.dumps(event), capture_output=True, text=True, check=True).stdout
    return json.loads(out) if out.strip() else None


def pre(path, command):
    return {'hook_event_name': 'PreToolUse', 'transcript_path': path, 'tool_name': 'Bash',
            'tool_input': {'command': command}, 'session_id': 's'}


class Thread(unittest.TestCase):
    def test_blocks_send_without_reread(self):
        t = transcript(('answer the client', ['echo hi'], ''))
        out = run(pre(t, 'send-message --to Ann@example.com --body @reply.txt'))
        self.assertEqual(out['hookSpecificOutput']['permissionDecision'], 'deny')
        self.assertIn('ann@example.com', out['hookSpecificOutput']['permissionDecisionReason'])

    def test_passes_after_reread_of_that_address(self):
        t = transcript(('answer the client', ['thread-check ann@example.com'], ''))
        self.assertIsNone(run(pre(t, 'send-message --to ann@example.com --body @reply.txt')))

    def test_reread_of_another_address_does_not_count(self):
        t = transcript(('answer the client', ['thread-check bob@example.com'], ''))
        out = run(pre(t, 'send-message --to ann@example.com --body @reply.txt'))
        self.assertEqual(out['hookSpecificOutput']['permissionDecision'], 'deny')

    def test_reread_in_an_earlier_turn_counts(self):
        t = transcript(('look at the thread', ['thread-check ann@example.com'], 'read.'),
                       ('send it', [], ''))
        self.assertIsNone(run(pre(t, 'send-message --to ann@example.com --body @reply.txt')))

    def test_preview_call_is_exempt(self):
        t = transcript(('show me', [], ''))
        self.assertIsNone(run(pre(t, 'send-message --preview --to ann@example.com')))

    def test_earlier_help_does_not_exempt_a_later_send(self):
        t = transcript(('answer', ['git --help'], ''))
        out = run(pre(t, 'send-message --to ann@example.com --body @reply.txt'))
        self.assertEqual(out['hookSpecificOutput']['permissionDecision'], 'deny')

    def test_send_without_recognizable_recipient_is_refused(self):
        t = transcript(('answer', ['thread-check ann@example.com'], ''))
        out = run(pre(t, 'send-message ann@example.com --body @reply.txt'))
        self.assertEqual(out['hookSpecificOutput']['permissionDecision'], 'deny')


class Deploy(unittest.TestCase):
    def stop(self, *commands, final='done'):
        t = transcript(('ship it', list(commands), final))
        return run({'hook_event_name': 'Stop', 'transcript_path': t, 'session_id': 's'})

    def test_blocks_unchecked_deploy(self):
        self.assertEqual(self.stop('npx wrangler deploy')['decision'], 'block')

    def test_check_before_deploy_does_not_count(self):
        self.assertEqual(self.stop('curl -s https://example.com', 'npx wrangler deploy')['decision'], 'block')

    def test_passes_when_checked_after(self):
        self.assertIsNone(self.stop('npx wrangler deploy', 'curl -s https://example.com/health'))

    def test_no_loop_when_already_sent_back(self):
        t = transcript(('ship it', ['npx wrangler deploy'], 'done'))
        self.assertIsNone(run({'hook_event_name': 'Stop', 'transcript_path': t, 'stop_hook_active': True}))


class Observation(unittest.TestCase):
    def test_observation_never_blocks_but_logs(self):
        t = transcript(('is there an invoice?', ['ls'], 'No trace of that invoice.'))
        log = tempfile.mktemp(suffix='.jsonl')
        self.assertIsNone(run({'hook_event_name': 'Stop', 'transcript_path': t}, log=log))
        with open(log) as f:
            rows = [json.loads(l) for l in f]
        self.assertEqual(rows[0]['guard'], 'search-before-absence')
        self.assertTrue(rows[0]['observation'])


class KillByPattern(unittest.TestCase):
    def test_pkill_refused_kill_pid_allowed(self):
        t = transcript(('stop the server', [], ''))
        self.assertEqual(run(pre(t, 'pkill -f node'))['hookSpecificOutput']['permissionDecision'], 'deny')
        self.assertIsNone(run(pre(t, 'kill 4242')))


if __name__ == '__main__':
    unittest.main()
