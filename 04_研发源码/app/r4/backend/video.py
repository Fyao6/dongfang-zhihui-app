"""Homepage video cards reuse the existing quotes content and revision lifecycle."""
import json
import re
import time
from urllib.parse import urlsplit
from uuid import uuid4

LANGUAGES = ('zh', 'zh-Hant', 'en', 'bo')
TEXT_FIELDS = ('zh', 'en', 'hant', 'bo', 'bannerLabel', 'bannerLabelEn', 'bannerLabelHant', 'bannerLabelBo',
               'description', 'descriptionEn', 'descriptionHant', 'descriptionBo', 'buttonLabel', 'buttonLabelEn', 'buttonLabelHant', 'buttonLabelBo')
TARGETS = ('academy', 'dailyCard', 'music', 'body', 'mind', 'lifeResult', 'service', 'membership')
MEDIA_RE = re.compile(r'^/api/media/[a-f0-9-]{36}$')


def init_schema(db):
    """No new content store; existing contents/revisions/audits are authoritative."""


def now():
    return time.time_ns() // 1_000_000


def dump(value):
    return json.dumps(value, ensure_ascii=False, separators=(',', ':'), allow_nan=False)


def valid_https(value):
    try:
        u = urlsplit(value)
        _ = u.port
        return bool(u.scheme == 'https' and u.hostname and not u.username and not u.password)
    except (TypeError, ValueError):
        return False


def validate_vtt(value, Error):
    if not isinstance(value, str) or len(value) > 20000:
        raise Error(400, '每个字幕文本最多20000字符。')
    text = value.lstrip('\ufeff').replace('\r\n', '\n').replace('\r', '\n').strip()
    if not re.match(r'^WEBVTT(?:[ \t][^\n]*)?\n', text + '\n'):
        raise Error(400, '字幕须为WEBVTT格式，不能只修改文件扩展名。')
    times = re.findall(r'^(?:(\d{2,}):)?(\d{2}):(\d{2})\.(\d{3})[ \t]+-->[ \t]+(?:(\d{2,}):)?(\d{2}):(\d{2})\.(\d{3})(?:[^\n]*)\n([^\n]+)', text, re.M)
    if not times or len(times) != sum('-->' in line for line in text.split('\n')):
        raise Error(400, '字幕需要至少一段有效时间轴与文字。')
    for cue in times:
        h1, m1, s1, f1, h2, m2, s2, f2, _ = cue
        if any(int(x) > 59 for x in (m1, s1, m2, s2)):
            raise Error(400, '字幕的分秒范围不正确。')
        start = (int(h1 or 0) * 3600 + int(m1) * 60 + int(s1)) * 1000 + int(f1)
        end = (int(h2 or 0) * 3600 + int(m2) * 60 + int(s2)) * 1000 + int(f2)
        if end <= start:
            raise Error(400, '字幕结束时间必须晚于开始时间。')
    return text + '\n'


def validate_video_item(item, status, Error):
    """Apply this hook to generic quotes saves AND revision restoration as well."""
    if not isinstance(item, dict):
        raise Error(400, '轮播内容须为对象。')
    if item.get('mediaType') != 'video':
        if item.get('mediaType') not in (None, '', 'image') or any(item.get(k) for k in ('mediaUrl', 'subtitleTracks', 'mediaReviewed', 'rightsNote')):
            raise Error(400, '带视频地址或字幕的轮播必须明确声明mediaType为video，不能通过改类型绕过发布校验。')
        return item
    if status not in ('draft', 'published', 'archived'):
        raise Error(400, '无效发布状态。')
    allowed = set(TEXT_FIELDS) | {'id', 'mediaType', 'mediaUrl', 'coverUrl', 'subtitleTracks', 'target', 'rightsNote', 'mediaReviewed', 'enabled'}
    if set(item) - allowed:
        raise Error(400, '视频轮播包含未知字段。')
    clean = {'id': item.get('id', ''), 'mediaType': 'video'}
    if not isinstance(clean['id'], str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,80}', clean['id']):
        raise Error(400, '内容编号须为字母、数字、下划线或连字符。')
    for field in TEXT_FIELDS:
        value = item.get(field, '')
        maximum = 1000 if field.startswith('description') else 200
        if not isinstance(value, str) or len(value.strip()) > maximum:
            raise Error(400, '轮播多语文字为空或超出长度。')
        clean[field] = value.strip()
    for field in ('mediaUrl', 'coverUrl'):
        value = item.get(field, '')
        if not isinstance(value, str) or len(value) > 1500 or value and not (MEDIA_RE.fullmatch(value) or valid_https(value)):
            raise Error(400, '视频和封面须为本站上传素材或无账号凭据的HTTPS地址。')
        clean[field] = value
    target = item.get('target', '')
    if not isinstance(target, str) or len(target) > 1500 or target and target not in TARGETS and not valid_https(target):
        raise Error(400, '跳转须为允许的APP页面或HTTPS地址。')
    clean['target'] = target
    tracks = item.get('subtitleTracks', [])
    if not isinstance(tracks, list) or len(tracks) > 4:
        raise Error(400, '字幕最多配置简繁英藏四条。')
    cleaned_tracks, seen = [], set()
    for track in tracks:
        if not isinstance(track, dict) or set(track) - {'lang', 'label', 'url', 'text'} or track.get('lang') not in LANGUAGES or track['lang'] in seen:
            raise Error(400, '字幕语言不正确或重复。')
        lang, url, text = track['lang'], track.get('url', ''), track.get('text', '')
        label = track.get('label', '')
        if not isinstance(label, str) or len(label) > 80 or bool(url) == bool(text):
            raise Error(400, '每条字幕须选择HTTPS地址或WEBVTT文本其中一种。')
        if url and (not isinstance(url, str) or len(url) > 1500 or not valid_https(url)):
            raise Error(400, '外部字幕须为HTTPS地址，并需在目标端验证CORS。')
        result = {'lang': lang, 'label': label}
        if url:
            result['url'] = url
        else:
            result['text'] = validate_vtt(text, Error)
        cleaned_tracks.append(result)
        seen.add(lang)
    clean['subtitleTracks'] = cleaned_tracks
    if type(item.get('enabled', True)) is not bool or type(item.get('mediaReviewed', False)) is not bool:
        raise Error(400, '启用和已审核标记须为布尔值。')
    clean['enabled'], clean['mediaReviewed'] = item.get('enabled', True), item.get('mediaReviewed', False)
    rights = item.get('rightsNote', '')
    if not isinstance(rights, str) or len(rights.strip()) > 2000:
        raise Error(400, '素材授权依据最多2000字符。')
    clean['rightsNote'] = rights.strip()
    if status == 'published' and (not clean['zh'] or not clean['mediaUrl'] or not clean['coverUrl'] or not clean['mediaReviewed'] or not clean['rightsNote'] or not {'zh', 'zh-Hant', 'en'} <= seen):
        raise Error(400, '正式发布需要真实视频、封面、简繁英字幕、已审标记与可核对的素材授权依据；资料未齐请存草稿。')
    if len(dump(clean)) > 90000:
        raise Error(400, '视频配置过长，请精简字幕。')
    return clean


def authorize_video_media(db, item, actor_id, Error):
    fields = (('mediaUrl', 'video/'), ('coverUrl', 'image/')) if item.get('mediaType') == 'video' else (('coverUrl', 'image/'),)
    for field, mime in fields:
        ref = item.get(field, '')
        if not MEDIA_RE.fullmatch(ref):
            continue
        row = db.execute('SELECT owner,mime FROM media WHERE id=?', (ref.rsplit('/', 1)[1],)).fetchone()
        if not row or not row['mime'].startswith(mime):
            raise Error(400, '已上传素材不存在或类型与视频/封面用途不符。')
        public = db.execute("SELECT 1 FROM contents WHERE status='published' AND json_extract(data,'$.creatorId') IS NULL AND (kind!='courses' OR COALESCE(json_extract(data,'$.access'),'public')!='member') AND (json_extract(data,'$.mediaUrl')=? OR json_extract(data,'$.coverUrl')=?) LIMIT 1", (ref, ref)).fetchone()
        if row['owner'] != actor_id and not public:
            raise Error(403, '不能把其他账号的私有素材发布为首页视频或封面。')


class Video:
    def __init__(self, store, handler, error, limiter):
        self.store, self.h, self.Error, self.rate = store, handler, error, limiter

    def fail(self, code, message):
        raise self.Error(code, message)

    def item(self, row):
        return {**json.loads(row['data']), '_status': row['status'], '_position': row['position'], '_updatedAt': row['updated']}

    def route(self, method, path):
        if path != '/api/admin/videos':
            return None
        user = self.h.require(('admin', 'operator', 'reviewer'))
        if method == 'GET':
            with self.store.connect() as db:
                rows = db.execute("SELECT * FROM contents WHERE kind='quotes' AND json_extract(data,'$.mediaType')='video' ORDER BY position,updated,id").fetchall()
            return {'items': [self.item(r) for r in rows], 'formalMediaPresent': any(r['status'] == 'published' for r in rows)}
        if method not in ('POST', 'PATCH'):
            self.fail(405, '不支持的操作。')
        self.h.require(('admin', 'operator'))
        self.rate('home-video-save:' + user['id'], 30)
        data = self.h.body()
        if set(data) - {'item', 'status', 'position', 'expectedUpdatedAt'}:
            self.fail(400, '视频管理请求包含未知字段。')
        status = data.get('status', 'draft')
        item = validate_video_item(data.get('item', {}), status, self.Error)
        if item.get('mediaType') != 'video':
            self.fail(400, '此入口仅管理视频；原图文轮播在原模块维护。')
        position = data.get('position', 0)
        if type(position) is not int or not -10000 <= position <= 10000:
            self.fail(400, '排序须为-10000至10000整数。')
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            old = db.execute("SELECT * FROM contents WHERE kind='quotes' AND id=?", (item['id'],)).fetchone()
            expected = data.get('expectedUpdatedAt')
            if type(expected) is not int or expected != (old['updated'] if old else 0):
                self.fail(409, '轮播已由其他操作更新，请重新读取后保存。')
            authorize_video_media(db, item, user['id'], self.Error)
            if old:
                db.execute('INSERT INTO revisions VALUES (?,?,?,?,?,?)', (str(uuid4()), user['id'], 'quotes', item['id'], dump(dict(old)), now()))
            updated = max(now(), (old['updated'] + 1) if old else 0)
            db.execute("INSERT INTO contents VALUES ('quotes',?,?,?,?,?) ON CONFLICT(kind,id) DO UPDATE SET data=excluded.data,status=excluded.status,position=excluded.position,updated=excluded.updated", (item['id'], dump(item), status, position, updated))
            self.store.audit(db, user['id'], 'video.' + status, item['id'], '视频配置已保存；素材实际可播放性须目标端验收。')
            row = db.execute("SELECT * FROM contents WHERE kind='quotes' AND id=?", (item['id'],)).fetchone()
        return {'item': self.item(row)}
