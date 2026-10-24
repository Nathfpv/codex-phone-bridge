"""Private newline JSON contract shared by Python 3.9 parent and voice worker."""
import json

VERSION = 2
LIMIT = 16384
KINDS = {'confirmed', 'ended_by_request', 'peer_closed', 'timed_out', 'limit'}


def message(options, message_type, **fields):
    return dict(v=VERSION, call_id=options['call_id'], type=message_type, **fields)


def decode(line, options):
    if not line or len(line) > LIMIT:
        raise ValueError('Invalid voice protocol length')
    data = json.loads(line)
    if (not isinstance(data, dict) or data.get('v') != VERSION
            or data.get('call_id') != options['call_id']
            or data.get('type') not in {'ready', 'outcome', 'outcome_ack', 'ready_to_close', 'error'}):
        raise ValueError('Voice protocol identity/version mismatch')
    if data['type'] == 'outcome':
        kind, answer = data.get('kind'), data.get('answer')
        if kind not in KINDS:
            raise ValueError('Invalid voice outcome')
        if kind == 'confirmed':
            if options.get('conversation') or not isinstance(answer, str) or not 1 <= len(answer) <= 2000:
                raise ValueError('Invalid confirmed voice outcome')
        elif 'answer' in data:
            raise ValueError('Non-decision outcome contains answer')
        if not isinstance(data.get('metrics', {}), dict):
            raise ValueError('Invalid voice metrics')
    return data
