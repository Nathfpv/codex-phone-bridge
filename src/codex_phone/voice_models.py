"""Voice model adapters. MAFFEO owns dialogue credentials and same-model routing."""
from urllib.parse import urlsplit
from pathlib import Path
import os
import stat

MAFFEO_URL = 'http://127.0.0.1:8081/v1'


def speech_model(options, http):
    backend = options.get('recognition_backend', 'livekit')
    if backend == 'livekit':
        from livekit.agents import inference
        return inference.STT(model='assemblyai/universal-streaming-multilingual',
                             language='de', http_session=http)
    if backend != 'groq':
        raise ValueError('Unknown recognition backend')
    path = Path.home()/'.groq-key'
    info = path.lstat()
    if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077):
        raise RuntimeError('Existing Groq credential must be an owner-only regular file')
    key = path.read_text().strip()
    if not key:
        raise RuntimeError('Existing Groq credential is empty')
    from livekit.plugins import groq
    return groq.STT(model='whisper-large-v3', api_key=key, language='de')


def dialogue_model(options, *, base_url=MAFFEO_URL):
    backend = options.get('dialogue_backend', 'livekit')
    if backend == 'livekit':
        from livekit.agents import inference
        return inference.LLM(model='google/gemma-4-31b-it',
                             extra_kwargs={'max_tokens': 512, 'reasoning_effort': 'none'})
    if backend != 'maffeo':
        raise ValueError('Unknown dialogue backend')
    url = urlsplit(base_url)
    if (url.scheme != 'http' or url.hostname != '127.0.0.1' or
            url.username or url.password or url.path != '/v1' or url.query or url.fragment):
        raise ValueError('MAFFEO dialogue requires an HTTP loopback /v1 endpoint')
    from livekit.plugins import openai
    return openai.LLM(model='gpt-oss-120b', base_url=base_url, api_key='local-loopback',
                      max_completion_tokens=512, reasoning_effort='low',
                      max_retries=0, parallel_tool_calls=False)
