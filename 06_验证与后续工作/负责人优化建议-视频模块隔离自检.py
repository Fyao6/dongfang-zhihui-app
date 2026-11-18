"""Video publishing checks in RAM. No original database, media download or network."""
from pathlib import Path
from contextlib import contextmanager
import ast
import copy
import importlib.util
import json
import sqlite3
import sys

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
BACK = ROOT / '04_研发源码/app/r4/backend'
spec = importlib.util.spec_from_file_location('isolated_home_video', BACK / 'video.py')
video = importlib.util.module_from_spec(spec)
spec.loader.exec_module(video)
tree = ast.parse((BACK / 'server.py').read_text(encoding='utf-8'))
store_class = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'Store')
core = next(n.args[0].value for n in ast.walk(store_class) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == 'executescript' and isinstance(n.args[0], ast.Constant))


class Error(Exception):
    def __init__(self, status, message):
        self.status, self.message = status, message


class Store:
    def __init__(self):
        self.db = sqlite3.connect(':memory:')
        self.db.row_factory = sqlite3.Row
        self.db.executescript(core)
        for uid, role in [('admin', 'admin'), ('operator', 'operator'), ('reviewer', 'reviewer'), ('private', 'user')]:
            self.db.execute('INSERT INTO users VALUES (?,?,?,?,?,?)', (uid, uid, 'synthetic-not-usable', uid, role, 1))
        self.db.commit()

    @contextmanager
    def connect(self):
        with self.db:
            yield self.db

    def audit(self, db, actor, action, target, detail=''):
        db.execute('INSERT INTO audits VALUES (?,?,?,?,?,?)', (str(video.uuid4()), actor, action, target, detail, 1))


class Handler:
    def __init__(self, store, uid):
        self.user = store.db.execute('SELECT * FROM users WHERE id=?', (uid,)).fetchone() if uid else None
        self.data = {}

    def require(self, roles=None):
        if not self.user:
            raise Error(401, 'login')
        if roles and self.user['role'] not in roles:
            raise Error(403, 'role')
        return self.user

    def body(self):
        return self.data


checks = []


def check(name, passed):
    assert passed, name
    checks.append({'name': name, 'passed': True})


def rejects(name, status, callback):
    try:
        callback()
    except Error as error:
        check(name, error.status == status)
    else:
        raise AssertionError(name + ' was not rejected')


store = Store()
handler = Handler(store, 'admin')
api = video.Video(store, handler, Error, lambda *args: None)
vtt = 'WEBVTT\n\n00:00.000 --> 00:02.000\nSYNTHETIC TEST SUBTITLE NOT A FORMAL INTRODUCTION\n'
item = {'id': 'fixture_intro', 'mediaType': 'video', 'zh': '隔离测试素材', 'en': 'Isolated test fixture', 'hant': '隔離測試素材', 'bo': 'ཚོད་ལྟ།', 'mediaUrl': 'https://media.example.invalid/fixture.mp4', 'coverUrl': 'https://media.example.invalid/fixture.jpg', 'subtitleTracks': [{'lang': lang, 'text': vtt} for lang in ('zh', 'zh-Hant', 'en')], 'mediaReviewed': True, 'rightsNote': 'Synthetic fixture only; no formal introduction produced', 'enabled': True}
legacy = {'id': 'old_quote', 'zh': '原图文', 'coverUrl': ''}
check('legacy image and text record remains unchanged', video.validate_video_item(legacy, 'published', Error) is legacy)
rejects('deleting mediaType cannot bypass video publishing validation', 400, lambda: video.validate_video_item({k: v for k, v in item.items() if k != 'mediaType'}, 'published', Error))
rejects('changing mediaType to image cannot bypass video publishing validation', 400, lambda: video.validate_video_item({**item, 'mediaType': 'image'}, 'published', Error))
check('empty video configuration can remain a draft', video.validate_video_item({'id': 'empty', 'mediaType': 'video'}, 'draft', Error)['subtitleTracks'] == [])
rejects('empty placeholder cannot be published', 400, lambda: video.validate_video_item({'id': 'empty', 'mediaType': 'video'}, 'published', Error))
check('complete fixture configuration validates without fetching any URL', video.validate_video_item(item, 'published', Error)['zh'] == item['zh'])
for name, change in [('missing cover', {'coverUrl': ''}), ('missing rights', {'rightsNote': ''}), ('unreviewed', {'mediaReviewed': False}), ('incomplete subtitle languages', {'subtitleTracks': item['subtitleTracks'][:2]})]:
    rejects('publish rejects '+name, 400, lambda change=change: video.validate_video_item({**item, **change}, 'published', Error))
rejects('subtitle header alone is not a real subtitle', 400, lambda: video.validate_vtt('WEBVTT\n', Error))
rejects('reversed subtitle timestamps rejected', 400, lambda: video.validate_vtt('WEBVTT\n\n00:02.000 --> 00:01.000\nfixture\n', Error))
rejects('subtitle minute bounds validated', 400, lambda: video.validate_vtt('WEBVTT\n\n00:70.000 --> 02:00.000\nfixture\n', Error))
rejects('one valid cue cannot hide malformed other cues', 400, lambda: video.validate_vtt(vtt+'\nBAD --> INVALID\nnot valid\n', Error))
rejects('duplicate subtitle languages rejected', 400, lambda: video.validate_video_item({**item, 'subtitleTracks': [item['subtitleTracks'][0]]*2}, 'draft', Error))
rejects('text and URL cannot both be active subtitle sources', 400, lambda: video.validate_video_item({**item, 'subtitleTracks': [{'lang': 'zh', 'url': 'https://example.invalid/a.vtt', 'text': vtt}]}, 'draft', Error))
for source in ['javascript:alert(1)', 'http://example.invalid/a.mp4', 'https://user:password@example.invalid/a.mp4', 'https://example.invalid:bad/a.mp4']:
    rejects('unsafe media address blocked '+source.split(':')[0], 400, lambda source=source: video.validate_video_item({**item, 'mediaUrl': source}, 'draft', Error))
handler.data = {'item': item, 'status': 'published', 'position': 1, 'expectedUpdatedAt': 0}
saved = api.route('POST', '/api/admin/videos')['item']
check('video stored in original quotes collection', bool(store.db.execute("SELECT 1 FROM contents WHERE kind='quotes' AND id='fixture_intro'").fetchone()))
check('video list reflects actual stored item', api.route('GET', '/api/admin/videos')['items'][0]['id'] == item['id'])
rejects('stale expected update timestamp rejected', 409, lambda: api.route('POST', '/api/admin/videos'))
handler.data = {'item': {**item, 'description': 'updated'}, 'status': 'draft', 'position': -1, 'expectedUpdatedAt': saved['_updatedAt']}
updated = api.route('PATCH', '/api/admin/videos')['item']
check('updated timestamps strictly advance', updated['_updatedAt'] > saved['_updatedAt'])
check('previous actual content saved in existing revision table', store.db.execute("SELECT count(*) FROM revisions WHERE kind='quotes' AND item_id='fixture_intro'").fetchone()[0] == 1)
private_id = 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa'
cover_id = 'cccccccc-cccc-cccc-cccc-cccccccccccc'
with store.connect() as db:
    db.execute('INSERT INTO media VALUES (?,?,?,?,?,?)', (private_id, 'private', 'video/mp4', 'private.mp4', b'not-used-as-playable-media', 1))
    db.execute('INSERT INTO media VALUES (?,?,?,?,?,?)', (cover_id, 'admin', 'image/jpeg', 'fixture.jpg', b'not-used-as-playable-media', 1))
private = {**item, 'id': 'private_leak', 'mediaUrl': '/api/media/'+private_id, 'coverUrl': '/api/media/'+cover_id}
handler.data = {'item': private, 'status': 'draft', 'position': 0, 'expectedUpdatedAt': 0}
rejects('admin cannot publish another account private upload by guessing URL', 403, lambda: api.route('POST', '/api/admin/videos'))
with store.connect() as db:
    db.execute("INSERT INTO contents VALUES ('quotes','mere_mention',?,'published',0,1)", (json.dumps({'zh': 'description only', 'description': '/api/media/'+private_id}),))
rejects('textual mention is not a media publication grant', 403, lambda: api.route('POST', '/api/admin/videos'))
member_cover = 'dddddddd-dddd-dddd-dddd-dddddddddddd'
with store.connect() as db:
    db.execute('INSERT INTO media VALUES (?,?,?,?,?,?)', (member_cover, 'private', 'image/jpeg', 'member-only.jpg', b'not-used-as-playable-media', 1))
    db.execute("INSERT INTO contents VALUES ('courses','member_private',?,'published',0,1)", (json.dumps({'zh': 'synthetic member course', 'access': 'member', 'mediaUrl': '/api/media/'+private_id, 'coverUrl': '/api/media/'+member_cover}),))
rejects('published member-course video is not public reusable media', 403, lambda: api.route('POST', '/api/admin/videos'))
handler.data = {'item': {**item, 'id': 'member_cover_leak', 'coverUrl': '/api/media/'+member_cover}, 'status': 'draft', 'position': 0, 'expectedUpdatedAt': 0}
rejects('published member-course cover is not a public media grant', 403, lambda: api.route('POST', '/api/admin/videos'))
with store.connect() as db:
    rejects('legacy cover cannot hide a private video MIME', 400, lambda: video.authorize_video_media(db, {'id': 'legacy_video_cover', 'coverUrl': '/api/media/'+private_id}, 'admin', Error))
handler.data = {'item': {**item, 'id': 'wrong_type', 'mediaUrl': '/api/media/'+cover_id}, 'status': 'draft', 'position': 0, 'expectedUpdatedAt': 0}
rejects('uploaded image cannot be used as video MIME', 400, lambda: api.route('POST', '/api/admin/videos'))
review = video.Video(store, Handler(store, 'reviewer'), Error, lambda *args: None)
rejects('reviewer cannot write video configuration', 403, lambda: review.route('POST', '/api/admin/videos'))
check('reviewer can read existing video metadata', len(review.route('GET', '/api/admin/videos')['items']) == 1)
rejects('anonymous cannot read administration media list', 401, lambda: video.Video(store, Handler(store, None), Error, lambda *args: None).route('GET', '/api/admin/videos'))
check('unrelated routes are not intercepted', api.route('GET', '/api/unrelated') is None)
result = {'kind': 'isolated-in-memory-video-checks', 'passed': len(checks), 'failed': 0, 'originalDatabaseOpened': False, 'networkRequests': 0, 'formalIntroductionProduced': False, 'checks': checks}
(ROOT/'06_验证与后续工作/负责人优化建议-视频模块隔离自检.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({'passed': len(checks), 'failed': 0}))
