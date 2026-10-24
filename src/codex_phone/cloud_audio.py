"""Isolate the optional modern voice SDK from the Python 3.9 SIP controller."""
import asyncio
import json
import os
import sqlite3
import time
import uuid
from .worker_protocol import VERSION, message, decode
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
        if self.proc.stdin and not self.proc.stdin.is_closing():
            self.proc.stdin.close()
        if self.proc.returncode is None:
            try:
                await asyncio.wait_for(self.proc.wait(), 3)
            except asyncio.TimeoutError:
                self.proc.terminate()
                try:
                    await asyncio.wait_for(self.proc.wait(), 2)
                except asyncio.TimeoutError:
                    self.proc.kill()
                    await self.proc.wait()
        if getattr(self, 'stderr_task', None):
            await self.stderr_task


def log_worker(event, stage=None, error=None):
    # Only allowlisted fields; never copy raw worker stderr into logs.
    path = home() / 'voice-worker.jsonl'
    if path.exists() and path.stat().st_size > 131072:
        previous = path.with_suffix('.previous.jsonl')
        path.replace(previous)
    fd = os.open(str(path), os.O_WRONLY | os.O_APPEND | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'a') as f:
        f.write(json.dumps({'time': time.time(), 'event': event,
                            'stage': stage, 'error': error}) + '\n')


async def drain_worker_errors(stream):
    # Bounded chunks prevent malformed/untrusted stderr from exhausting memory.
    pending = b''
    while True:
        chunk = await stream.read(4096)
        if not chunk:
            return
        pending += chunk
        while b'\n' in pending:
            line, pending = pending.split(b'\n', 1)
            try:
                value = json.loads(line)
                stage = value.get('stage')
                error = value.get('error')
                if stage not in {'credentials', 'models', 'session_start', 'preparing_greeting',
                                 'sip_audio', 'conversation', 'startup'}:
                    stage = 'unknown'
                if error not in {'RuntimeError', 'ValueError', 'CancelledError', 'TimeoutError',
                                 'OSError', 'APIConnectionError', 'APIStatusError'}:
                    error = 'WorkerError'
                log_worker('worker_failed', stage, error)
            except (ValueError, AttributeError):
                log_worker('worker_stderr_redacted', 'unknown', 'WorkerError')
        if len(pending) > 8192:
            pending = b''
            log_worker('worker_stderr_redacted', 'unknown', 'WorkerError')


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
    options = dict(v=VERSION, call_id=str(uuid.uuid4()), project_id=voice['project_id'], voice_id=voice['voice_id'],
                   synthesis_profile=voice.get('synthesis_profile', 'fish'),
                   dialogue_backend=cfg.get('dialogue_backend', 'livekit'),
                   recognition_backend=cfg.get('recognition_backend', 'livekit'),
                   rx_fd=sip.rx.fileno(), tx_fd=sip.tx.fileno(), tx_path=sip.tx_path,
                   status_path=str(home() / 'cloud-status.json'), preconnect=True,
                   question=question, conversation=cfg.get('phone_conversation',False), seconds=min(voice.get('max_call_seconds', 300), 300))
    proc = await asyncio.create_subprocess_exec(
        str(python), '-m', 'codex_phone.cloud_voice', env=env,
        pass_fds=(sip.rx.fileno(), sip.tx.fileno()),
        stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE, limit=32768)
    prepared = PreparedVoice(proc, options)
    prepared.stderr_task = asyncio.create_task(drain_worker_errors(proc.stderr))
    log_worker('worker_started', 'startup')
    try:
        proc.stdin.write(json.dumps(options).encode() + b'\n')
        await proc.stdin.drain()
        ready = decode(await asyncio.wait_for(proc.stdout.readline(), 45), options)
        if ready['type'] != 'ready':
            raise RuntimeError('Cloud preparation failed')
        return prepared
    except BaseException:
        await prepared.close()
        raise


async def converse(sip, question, cfg, prepared=None, on_outcome=None):
    prepared = prepared or await prepare_voice(sip, question, cfg)
    proc, options = prepared.proc, prepared.options
    task = None
    disconnected = None
    outcome = None
    close_ready = False
    metrics = {}
    try:
        from pathlib import Path
        deadline = asyncio.get_running_loop().time() + 12
        while not Path(sip.tx_path).exists():
            if sip.disconnected.is_set() or asyncio.get_running_loop().time() > deadline:
                raise RuntimeError('SIP media source not ready after connection')
            await asyncio.sleep(.025)
        proc.stdin.write(json.dumps({'connected': True,
                                    'connected_at': options.get('connected_at', time.monotonic())}).encode()+b'\n')
        await proc.stdin.drain()
        deadline = asyncio.get_running_loop().time() + options['seconds'] + 20
        disconnected = asyncio.create_task(sip.disconnected.wait())
        peer_closed = False
        while asyncio.get_running_loop().time() < deadline:
            task = asyncio.create_task(proc.stdout.readline())
            waits = [task] if peer_closed else [task, disconnected]
            done, _ = await asyncio.wait(waits, timeout=max(0, deadline-asyncio.get_running_loop().time()),
                                         return_when=asyncio.FIRST_COMPLETED)
            if disconnected in done and not peer_closed:
                peer_closed = True
                deadline = min(deadline, asyncio.get_running_loop().time()+1.5)
            if task not in done:
                if peer_closed:
                    try:
                        line = await asyncio.wait_for(task, max(.01, deadline-asyncio.get_running_loop().time()))
                    except asyncio.TimeoutError:
                        break
                    except ValueError:
                        if outcome is not None:
                            metrics['cleanup_error'] = 'protocol'
                            break
                        raise RuntimeError('Invalid cloud voice protocol') from None
                else:
                    break
            else:
                try:
                    line = task.result()
                except ValueError:
                    if outcome is not None:
                        metrics['cleanup_error'] = 'protocol'
                        break
                    raise RuntimeError('Invalid cloud voice protocol') from None
            if not line:
                break
            try:
                data = decode(line, options)
            except (ValueError, asyncio.LimitOverrunError):
                if outcome is not None:
                    metrics['cleanup_error'] = 'protocol'
                    break
                raise RuntimeError('Invalid cloud voice protocol') from None
            if data['type'] == 'error':
                if outcome is not None:
                    metrics['cleanup_error'] = 'worker'
                    break
                raise RuntimeError('Cloud voice worker failed at ' + str(data.get('stage', 'unknown')))
            if data['type'] == 'outcome':
                if outcome is not None:
                    continue  # same call receipt is delivered at most once
                outcome = data
                metrics.update(data.get('metrics', {}))
                if on_outcome is not None:
                    await on_outcome(data.get('answer'))
                try:
                    proc.stdin.write(json.dumps(message(options, 'outcome_ack')).encode()+b'\n')
                    await proc.stdin.drain()
                except (BrokenPipeError, ConnectionResetError):
                    metrics['cleanup_error'] = 'ack'
                    break
                deadline = min(deadline, asyncio.get_running_loop().time()+4)
            elif data['type'] == 'ready_to_close':
                if outcome is None:
                    raise RuntimeError('Voice close without outcome')
                close_ready = True
                break
            else:
                raise RuntimeError('Unexpected voice protocol message')
        if outcome is None:
            if peer_closed:
                metrics['outcome'] = 'peer_closed'
                return None, metrics
            raise RuntimeError('Cloud conversation ended without outcome')
        metrics['outcome'] = outcome['kind']
        metrics['farewell_completed'] = close_ready
        return outcome.get('answer'), metrics
    finally:
        for pending in (task, disconnected):
            if pending and not pending.done():
                pending.cancel()
        # Hang up before stopping the worker, even on cancellation/error.
        if hasattr(sip, 'hangup_and_wait'):
            metrics['local_dialog_closed'] = await sip.hangup_and_wait()
        await prepared.close()
        await asyncio.gather(*(t for t in (task, disconnected) if t), return_exceptions=True)
