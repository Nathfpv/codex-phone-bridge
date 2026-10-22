"""Bounded preflight, not a promise of provider quota or iPhone delivery."""
from pathlib import Path
import os
import shutil
import stat
import time
import urllib.request
import json
from .storage import ROOT
from .cloud_audio import allowance_status
from .sip import validate_uri


def call_readiness(cfg, bridge_state):
    budget = allowance_status(cfg)
    voice = cfg.get('cloud_voice', {})
    try:
        validate_uri(cfg.get('mac_uri')); validate_uri(cfg.get('iphone_uri'))
        sip_valid = bool(cfg.get('password')) and cfg['mac_uri'] != cfg['iphone_uri']
    except ValueError:
        sip_valid = False
    checks = {'budget': budget['budget_allows_call'], 'bridge_idle': bridge_state == 'IDLE',
              'sip_configuration': sip_valid, 'sip_binary': bool(shutil.which('baresip')),
              'voice_environment': (ROOT/'.local/voice-venv/bin/python').is_file(),
              'native_modules': all((ROOT/'.local/modules'/p).is_file() for p in ('phoneaudio.so','phonecontrol.so')),
              'voice_configuration': bool(cfg.get('voice_backend') == 'livekit' and voice.get('project_id')
                                           and voice.get('voice_id') and voice.get('free_plan_verified')),
              'outside_quiet_hours': time.localtime().tm_hour not in cfg.get('quiet_hours', [])}
    if cfg.get('recognition_backend') == 'groq':
        try:
            info=(Path.home()/'.groq-key').lstat()
            checks['groq_credential'] = bool(stat.S_ISREG(info.st_mode) and info.st_uid == os.getuid()
                                              and not info.st_mode & 0o077 and info.st_size)
        except OSError:
            checks['groq_credential'] = False
    elif cfg.get('recognition_backend', 'livekit') != 'livekit':
        checks['recognition_backend'] = False
    if cfg.get('dialogue_backend') == 'maffeo':
        try:
            with urllib.request.urlopen('http://127.0.0.1:8081/health', timeout=2) as response:
                checks['maffeo_router'] = response.status == 200 and json.load(response).get('status') == 'ok'
        except (OSError, ValueError):
            checks['maffeo_router'] = False
    elif cfg.get('dialogue_backend', 'livekit') != 'livekit':
        checks['dialogue_backend'] = False
    return {**budget, 'can_call': all(checks.values()), 'readiness_checks': checks,
            'readiness_scope': 'preflight_only; provider connection and iPhone delivery not guaranteed'}
