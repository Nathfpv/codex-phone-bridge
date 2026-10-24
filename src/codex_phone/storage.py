import json
import os
import sqlite3
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

def home():
    p = Path(os.environ.get('CODEX_PHONE_HOME', str(ROOT / '.local' / 'runtime'))).resolve()
    p.mkdir(parents=True, exist_ok=True, mode=0o700)
    if p.is_symlink() or p.stat().st_uid != os.getuid():
        raise ValueError('Unsafe runtime directory')
    p.chmod(0o700)
    return p

def private_json(path, data):
    tmp = path.with_suffix('.tmp')
    fd = os.open(str(tmp), os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'w') as f:
        json.dump(data, f, indent=2)
    tmp.chmod(0o600)
    tmp.replace(path)

def config():
    p = home() / 'config.json'
    if not p.exists():
        raise RuntimeError('BLOCKED_BY_USER: run codex-phone config in your local terminal')
    if p.stat().st_mode & 0o077:
        raise RuntimeError('Config must have mode 0600')
    return json.loads(p.read_text())

class Store:
    def __init__(self, path=None):
        self.db = sqlite3.connect(str(path or home() / 'state.sqlite3'))
        self.db.row_factory = sqlite3.Row
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.executescript('''
        CREATE TABLE IF NOT EXISTS sessions (id TEXT PRIMARY KEY, cwd TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS questions (
          id TEXT PRIMARY KEY, session_id TEXT NOT NULL, turn_id TEXT NOT NULL,
          request_id TEXT NOT NULL, question TEXT NOT NULL, status TEXT NOT NULL,
          created REAL NOT NULL, deadline REAL NOT NULL, answer TEXT,
          UNIQUE(session_id,turn_id,request_id));
        CREATE TABLE IF NOT EXISTS calls (
          id TEXT PRIMARY KEY, question_id TEXT REFERENCES questions(id),
          status TEXT NOT NULL, started REAL NOT NULL, ended REAL, error TEXT);
        ''')
        self.db.commit()
        if path is None:
            (home() / 'state.sqlite3').chmod(0o600)
    def add(self, session, turn, request, question, deadline):
        qid = str(uuid.uuid4())
        self.db.execute('INSERT OR IGNORE INTO questions VALUES (?,?,?,?,?,?,?, ?,NULL)',
                        (qid, session, turn, str(request), question, 'PENDING', time.time(), deadline))
        self.db.commit()
        return dict(self.db.execute('SELECT * FROM questions WHERE session_id=? AND turn_id=? AND request_id=?',
                                    (session, turn, str(request))).fetchone())
    def pending(self):
        return [dict(x) for x in self.db.execute("SELECT * FROM questions WHERE status IN ('PENDING','WAITING','ORPHANED') ORDER BY created")]
    def set_question(self, qid, status, answer=None):
        # A confirmed receipt survives cancellation/recovery after its ACK.
        self.db.execute('''UPDATE questions SET status=?,answer=COALESCE(?,answer)
                           WHERE id=? AND NOT (status='ANSWERED' AND ? IN
                           ('ORPHANED','EXPIRED','WAITING','ENDED_NO_DECISION','COMPLETED'))''',
                        (status, answer, qid, status)); self.db.commit()
    def new_call(self, qid):
        cid = str(uuid.uuid4())
        self.db.execute('INSERT INTO calls VALUES (?,?,?,?,NULL,NULL)', (cid,qid,'DIALING',time.time())); self.db.commit()
        return cid
    def call_state(self, cid, status, error=None):
        self.db.execute('UPDATE calls SET status=?,ended=?,error=? WHERE id=?',
                        (status,time.time() if status in ('ENDING','FAILED') else None,error,cid)); self.db.commit()
    def recover(self):
        self.db.execute("UPDATE questions SET status='ORPHANED' WHERE status='WAITING'")
        self.db.execute("UPDATE questions SET status='EXPIRED' WHERE status IN ('PENDING','WAITING','ORPHANED') AND deadline<?",(time.time(),))
        self.db.execute("UPDATE calls SET status='FAILED',error='service_restart',ended=? WHERE ended IS NULL",(time.time(),))
        self.db.commit()
