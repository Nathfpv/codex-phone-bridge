"""Isolate the optional modern voice SDK from the Python 3.9 SIP controller."""
import asyncio
import json
import os
import sqlite3
import time
from .storage import ROOT, home


def provider_cap_verified(cfg):
    evidence = cfg.get('provider_plan_evidence', {})
    if not isinstance(evidence, dict):
        return False
    project = cfg.get('cloud_voice', {}).get('project_id')
    checked = evidence.get('checked_at')
    return bool(evidence.get('plan') == 'build' and evidence.get('source') == 'dashboard'
                and isinstance(project, str) and project and evidence.get('project_id') == project
                and isinstance(checked, (int, float)) and not isinstance(checked, bool)
                and 0 <= time.time()-checked < 7*86400)


def allowance_status(cfg):
    """Local attempts are audit data, never the provider's remaining credits."""
    path = home() / 'voice-budget.sqlite3'
    used = 0
    if path.exists():
        db = sqlite3.connect('file:'+str(path)+'?mode=ro', uri=True)
        try:
            used = db.execute('SELECT COUNT(*) FROM reservations WHERE month=?',
                              (time.strftime('%Y-%m', time.gmtime()),)).fetchone()[0]
        finally:
            db.close()
    verified = provider_cap_verified(cfg)
    invalid_evidence = bool(cfg.get('provider_plan_evidence')) and not verified
    return {'local_calls_used': used, 'local_monthly_cap': None if verified else 12,
            'budget_allows_call': not invalid_evidence and (verified or used < 12),
            'budget_block_reason': 'Build plan verification stale or mismatched' if invalid_evidence else
                                   'Legacy local safety cap reached' if not verified and used >= 12 else None,
            'provider_enforced_hard_cap': verified,
            'provider_plan': 'build' if verified else 'UNVERIFIED',
            'provider_plan_checked_at': cfg.get('provider_plan_evidence', {}).get('checked_at'),
            'provider_remaining_allowance': 'UNKNOWN'}


def reserve_allowance(cfg=None):
    """Conservative local cap, NOT a provider billing guarantee.

    Reserve a full call even after failure/restart. No automatic paid fallback.
    Other clients of the same cloud project are outside this local counter.
    """
    cfg = cfg or {}
    if cfg.get('provider_plan_evidence') and not provider_cap_verified(cfg):
        raise RuntimeError('Build plan verification stale or mismatched; recheck dashboard; no paid fallback')
    path = home() / 'voice-budget.sqlite3'
    db = sqlite3.connect(str(path), timeout=5)
    try:
        path.chmod(0o600)
        db.execute('CREATE TABLE IF NOT EXISTS reservations (month TEXT, created REAL)')
        db.execute('BEGIN IMMEDIATE')
        month = time.strftime('%Y-%m', time.gmtime())
        count = db.execute('SELECT COUNT(*) FROM reservations WHERE month=?', (month,)).fetchone()[0]
        if count >= 12 and not provider_cap_verified(cfg):
            raise RuntimeError('Local free-use safety limit reached; no paid fallback')
        db.execute('INSERT INTO reservations VALUES (?,?)', (month, time.time()))
        db.commit()
    finally:
        db.close()


class PreparedVoice:
    def __init__(self, proc, options):
        self.proc = proc
        self.options = options

    async def close(self):
        if self.proc.returncode is None:
            self.proc.terminate()
            try:
                await asyncio.wait_for(self.proc.wait(), 5)
            except asyncio.TimeoutError:
                self.proc.kill()
                await self.proc.wait()


async def prepare_voice(sip, question, cfg):
    """Warm the SDK and synthesize the first question before making the call."""
    python = ROOT / '.local/voice-venv/bin/python'
    if not python.exists():
        raise RuntimeError('Cloud voice environment not installed')
    voice = cfg.get('cloud_voice', {})
    if not voice.get('project_id') or not voice.get('voice_id') or not voice.get('free_plan_verified'):
        raise RuntimeError('Free LiveKit project and voice must be configured first')
    reserve_allowance(cfg)
    env = dict(os.environ, PYTHONPATH=str(ROOT / 'src'), OTEL_SDK_DISABLED='true')
    options = dict(project_id=voice['project_id'], voice_id=voice['voice_id'],
                   dialogue_backend=cfg.get('dialogue_backend', 'livekit'),
                   recognition_backend=cfg.get('recognition_backend', 'livekit'),
                   rx_fd=sip.rx.fileno(), tx_fd=sip.tx.fileno(), tx_path=sip.tx_path,
                   status_path=str(home() / 'cloud-status.json'), preconnect=True,
                   question=question, seconds=min(voice.get('max_call_seconds', 300), 300))
    proc = await asyncio.create_subprocess_exec(
        str(python), '-m', 'codex_phone.cloud_voice', env=env,
        pass_fds=(sip.rx.fileno(), sip.tx.fileno()),
        stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL)
    prepared = PreparedVoice(proc, options)
    try:
        proc.stdin.write(json.dumps(options).encode() + b'\n')
        await proc.stdin.drain()
        ready = json.loads(await asyncio.wait_for(proc.stdout.readline(), 45))
        if ready != {'ready': True}:
            raise RuntimeError('Cloud preparation failed: ' + ready.get('error', 'invalid response') +
                               ' at ' + ready.get('stage', 'startup'))
        return prepared
    except BaseException:
        await prepared.close()
        raise


async def converse(sip, question, cfg, prepared=None):
    prepared = prepared or await prepare_voice(sip, question, cfg)
    proc, options = prepared.proc, prepared.options
    task = None
    disconnected = None
    try:
        from pathlib import Path
        deadline = asyncio.get_running_loop().time() + 12
        while not Path(sip.tx_path).exists():
            if sip.disconnected.is_set() or asyncio.get_running_loop().time() > deadline:
                raise RuntimeError('SIP media source not ready after connection')
            await asyncio.sleep(.025)
        proc.stdin.write(json.dumps({'connected':True,
                                    'connected_at':options.get('connected_at',time.monotonic())}).encode()+b'\n')
        await proc.stdin.drain()
        proc.stdin.close()
        task = asyncio.create_task(proc.stdout.readline())
        disconnected = asyncio.create_task(sip.disconnected.wait())
        done, _ = await asyncio.wait([task, disconnected], timeout=options['seconds']+20,
                                     return_when=asyncio.FIRST_COMPLETED)
        if task not in done:
            raise RuntimeError('Call disconnected or cloud conversation timed out')
        stdout = task.result()
        if proc.returncode not in (None, 0) or len(stdout) > 16384:
            raise RuntimeError('Cloud voice worker failed')
        data = json.loads(stdout)
        if 'error' in data:
            raise RuntimeError('Cloud voice failed: ' + data['error'] + ' at ' + data.get('stage', 'unknown'))
        answer = data.get('answer')
        if not isinstance(answer, str) or not 1 <= len(answer) <= 2000:
            raise RuntimeError('No confirmed cloud decision')
        return answer, data.get('metrics', {})
    finally:
        if disconnected:
            disconnected.cancel()
        await prepared.close()
        await asyncio.gather(*(t for t in (task, disconnected) if t), return_exceptions=True)
