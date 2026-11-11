"""Account activity aggregates without personal content or historical backfill."""
from datetime import date, datetime, timedelta, timezone
import json
import re
import time
from urllib.parse import parse_qs, urlsplit

ZONE = timezone(timedelta(hours=8))
FEATURES = {'home': '首页', 'life': '生命地图', 'body': '身体地图', 'mind': '心智地图', 'practice': '禅修与练习', 'academy': '智慧馆', 'community': '社群', 'ai': 'AI对话', 'profile': '我的', 'checkin': '签到', 'cards': '智慧卡片', 'music': '音乐', 'device': '设备', 'other': '其他页面'}
MEMBERS = "u.role IN ('user','teacher')"
SCHEMA = '''CREATE TABLE IF NOT EXISTS activity_daily(user_id TEXT NOT NULL REFERENCES users(id),day TEXT NOT NULL,feature TEXT NOT NULL,visits INTEGER NOT NULL,first_seen INTEGER NOT NULL,last_seen INTEGER NOT NULL,last_visit INTEGER NOT NULL,PRIMARY KEY(user_id,day,feature));
CREATE INDEX IF NOT EXISTS activity_daily_day ON activity_daily(day,user_id);'''
UPSERT = '''INSERT INTO activity_daily VALUES (?,?,?,?,?,?,?) ON CONFLICT(user_id,day,feature) DO UPDATE SET
visits=activity_daily.visits+CASE WHEN excluded.visits=1 AND (activity_daily.last_visit=0 OR excluded.last_visit-activity_daily.last_visit>=30000) THEN 1 ELSE 0 END,
last_seen=max(activity_daily.last_seen,excluded.last_seen),
last_visit=CASE WHEN excluded.visits=1 AND (activity_daily.last_visit=0 OR excluded.last_visit-activity_daily.last_visit>=30000) THEN excluded.last_visit ELSE activity_daily.last_visit END'''


def now():
    return time.time_ns() // 1_000_000


def iso(value):
    return datetime.fromtimestamp(value / 1000, timezone.utc).isoformat()


def day_at(value):
    return datetime.fromtimestamp(value / 1000, ZONE).date()


def midnight(value):
    return int(datetime.combine(value, datetime.min.time(), ZONE).timestamp() * 1000)


def init_schema(db):
    db.executescript(SCHEMA)
    db.execute('INSERT OR IGNORE INTO settings VALUES (?,?)', ('analytics_started_v1', json.dumps({'startedAt': now()})))


def bucket_start(value, grain):
    if grain == 'week':
        return value - timedelta(days=value.weekday())
    if grain == 'month':
        return value.replace(day=1)
    if grain == 'year':
        return value.replace(month=1, day=1)
    return value


def next_bucket(value, grain):
    if grain == 'week':
        return value + timedelta(days=7)
    if grain == 'month':
        return date(value.year + (value.month == 12), value.month % 12 + 1, 1)
    if grain == 'year':
        return date(value.year + 1, 1, 1)
    return value + timedelta(days=1)


class Analytics:
    def __init__(self, store, handler, error, limiter):
        self.store, self.h, self.Error, self.rate = store, handler, error, limiter

    def fail(self, status, message):
        raise self.Error(status, message)

    def route(self, method, path):
        if path not in ('/api/analytics/activity', '/api/admin/analytics'):
            return None
        if path == '/api/analytics/activity':
            if method != 'POST':
                self.fail(405, '不支持的操作。')
            self.h.require()
            body = self.h.body()
            feature, kind = body.get('feature'), body.get('kind', 'visit')
            if set(body) - {'feature', 'kind'} or not isinstance(feature, str) or feature not in FEATURES or kind not in ('visit', 'heartbeat'):
                self.fail(400, '统计仅接受指定功能及访问或心跳事件。')
            if self.h.user['role'] not in ('user', 'teacher'):
                return {'ok': True, 'ignored': True}
            uid, stamp = self.h.user['id'], now()
            self.rate('analytics:' + uid, 180)
            visit = int(kind == 'visit')
            with self.store.connect() as db:
                db.execute(UPSERT, (uid, day_at(stamp).isoformat(), feature, visit, stamp, stamp, stamp if visit else 0))
            return {'ok': True}
        if method != 'GET':
            self.fail(405, '不支持的操作。')
        self.h.require(('admin', 'operator'))
        return self.report()

    def report(self):
        stamp = now()
        today = day_at(stamp)
        params = parse_qs(urlsplit(self.h.path).query, keep_blank_values=True)
        if set(params) - {'start', 'end', 'grain'} or any(len(v) != 1 for v in params.values()):
            self.fail(400, '统计筛选参数无效。')

        def parse_day(key, fallback):
            value = params.get(key, [fallback.isoformat()])[0]
            try:
                if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
                    raise ValueError()
                result = date.fromisoformat(value)
                if result.isoformat() != value or result.year < 1970:
                    raise ValueError()
                return result
            except ValueError:
                self.fail(400, '日期须为合法的YYYY-MM-DD，且不早于1970年。')

        start, end = parse_day('start', today - timedelta(days=29)), parse_day('end', today)
        grain = params.get('grain', ['day'])[0]
        if grain not in ('day', 'week', 'month', 'year') or start > end or end > today or (end - start).days >= 3660:
            self.fail(400, '请选择不含未来日期、最长3660天的有效日期范围和统计周期。')
        start_s, end_s, today_s = start.isoformat(), end.isoformat(), today.isoformat()
        bucket_sql = {'day': '{x}', 'week': "date({x},'-'||((CAST(strftime('%w',{x}) AS INTEGER)+6)%7)||' days')", 'month': "substr({x},1,7)||'-01'", 'year': "substr({x},1,4)||'-01-01'"}[grain]
        with self.store.connect() as db:
            since = int(json.loads(db.execute("SELECT data FROM settings WHERE key='analytics_started_v1'").fetchone()['data'])['startedAt'])

            def coverage(first, last):
                if midnight(last + timedelta(days=1)) <= since:
                    return 'uncollected'
                return 'complete' if midnight(first) >= since and midnight(last + timedelta(days=1)) <= stamp else 'partial'

            state = coverage(start, end)
            summary_row = db.execute(f'''SELECT count(DISTINCT a.user_id) activeUsers,coalesce(sum(a.visits),0) visits FROM activity_daily a JOIN users u ON u.id=a.user_id WHERE {MEMBERS} AND a.day>=? AND a.day<=? AND a.first_seen<=?''', (start_s, end_s, stamp)).fetchone()
            users_row = db.execute(f'''SELECT count(*) registeredUsers,coalesce(sum(CASE WHEN u.created>=? AND u.created<=? THEN 1 ELSE 0 END),0) newUsers FROM users u WHERE {MEMBERS} AND u.created<=?''', (midnight(start), min(stamp, midnight(end + timedelta(days=1)) - 1), stamp)).fetchone()
            summary = dict(users_row)
            summary.update(activeUsers=summary_row['activeUsers'] if state != 'uncollected' else None, visits=summary_row['visits'] if state != 'uncollected' else None, coverage=state)
            starts = {'day': today, 'week': bucket_start(today, 'week'), 'month': bucket_start(today, 'month'), 'year': bucket_start(today, 'year')}
            window_row = db.execute(f'''SELECT {','.join('count(DISTINCT CASE WHEN a.day>=? THEN a.user_id END) AS "' + key + '"' for key in starts)} FROM activity_daily a JOIN users u ON u.id=a.user_id WHERE {MEMBERS} AND a.day>=? AND a.day<=? AND a.first_seen<=?''', (*[d.isoformat() for d in starts.values()], min(starts.values()).isoformat(), today_s, stamp)).fetchone()
            windows = {key: dict(start=first.isoformat(), end=today_s, activeUsers=window_row[key] if coverage(first, today) != 'uncollected' else None, coverage=coverage(first, today)) for key, first in starts.items()}
            event_rows = {r['bucket']: dict(r) for r in db.execute(f'''SELECT {bucket_sql.format(x='a.day')} bucket,count(DISTINCT a.user_id) activeUsers,coalesce(sum(a.visits),0) visits FROM activity_daily a JOIN users u ON u.id=a.user_id WHERE {MEMBERS} AND a.day>=? AND a.day<=? AND a.first_seen<=? GROUP BY bucket''', (start_s, end_s, stamp))}
            user_day = "date(u.created/1000,'unixepoch','+8 hours')"
            new_rows = {r['bucket']: r['n'] for r in db.execute(f'''SELECT {bucket_sql.format(x=user_day)} bucket,count(*) n FROM users u WHERE {MEMBERS} AND u.created>=? AND u.created<=? GROUP BY bucket''', (midnight(start), min(stamp, midnight(end + timedelta(days=1)) - 1)))}
            trend, cursor = [], start
            while cursor <= end:
                natural = bucket_start(cursor, grain)
                last = min(end, next_bucket(natural, grain) - timedelta(days=1))
                covered, row = coverage(cursor, last), event_rows.get(natural.isoformat(), {})
                trend.append(dict(date=cursor.isoformat(), end=last.isoformat(), activeUsers=row.get('activeUsers', 0) if covered != 'uncollected' else None, newUsers=new_rows.get(natural.isoformat(), 0), visits=row.get('visits', 0) if covered != 'uncollected' else None, coverage=covered))
                cursor = last + timedelta(days=1)
            feature_rows = {r['feature']: dict(r) for r in db.execute(f'''SELECT a.feature,count(DISTINCT a.user_id) activeUsers,coalesce(sum(a.visits),0) visits FROM activity_daily a JOIN users u ON u.id=a.user_id WHERE {MEMBERS} AND a.day>=? AND a.day<=? AND a.first_seen<=? GROUP BY a.feature''', (start_s, end_s, stamp))}
            features = [dict(id=key, label=label, activeUsers=feature_rows.get(key, {}).get('activeUsers', 0) if state != 'uncollected' else None, visits=feature_rows.get(key, {}).get('visits', 0) if state != 'uncollected' else None) for key, label in FEATURES.items()]
            retention = []
            for days in (1, 7):
                row = db.execute(f'''WITH cohort AS (SELECT u.id,{user_day} day FROM users u WHERE {MEMBERS} AND u.created>=? AND u.created>=? AND u.created<=? AND date({user_day},?)<?) SELECT count(*) eligibleUsers,coalesce(sum(CASE WHEN EXISTS(SELECT 1 FROM activity_daily a WHERE a.user_id=c.id AND a.day=date(c.day,?)) THEN 1 ELSE 0 END),0) returnedUsers FROM cohort c''', (since, midnight(start), min(stamp, midnight(end + timedelta(days=1)) - 1), f'+{days} days', today_s, f'+{days} days')).fetchone()
                retention.append(dict(days=days, eligibleUsers=row['eligibleUsers'], returnedUsers=row['returnedUsers'], rate=round(row['returnedUsers'] * 100 / row['eligibleUsers'], 2) if row['eligibleUsers'] else None))
        return dict(timezone='Asia/Shanghai', generatedAt=iso(stamp), collectedSince=iso(since), range=dict(start=start_s, end=end_s, grain=grain), windows=windows, summary=summary, trend=trend, features=features, retention=retention)
