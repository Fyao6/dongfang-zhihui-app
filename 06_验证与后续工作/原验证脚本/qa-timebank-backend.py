from pathlib import Path
import concurrent.futures
from datetime import datetime, timezone
import importlib.util
import json
import tempfile

root=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('timebank_server', root/'r4/backend/server.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
checks=[]

def millis(iso):
    return int(datetime.fromisoformat(iso).timestamp()*1000)

with tempfile.TemporaryDirectory(prefix='timebank-test-',dir=root/'tmp') as temp:
    db=Path(temp)/'bank.sqlite3';ledger=module.Ledger(db)
    module.now_ms=lambda:millis('2026-10-14T15:59:50+00:00')
    first=ledger.action('start','Asia/Shanghai','start-1')
    assert first['running'] and len(first['runs'])==1
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        list(pool.map(lambda i:ledger.action('start','Asia/Shanghai',f'duplicate-{i}'),range(6)))
    assert len(ledger.state()['runs'])==1
    checks.append('Concurrent starts create one active run')
    module.now_ms=lambda:millis('2026-10-14T16:00:20+00:00')
    live=ledger.state();assert live['summary']['totalMs']==30000
    assert live['summary']['days']=={'2026-10-14':10000,'2026-10-15':20000}
    checks.append('Hidden/background time accrues from start; local midnight splits exactly')
    stopped=ledger.action('pause','Asia/Shanghai','pause-1')
    module.now_ms=lambda:millis('2026-10-14T16:01:20+00:00')
    assert ledger.state()['summary']['totalMs']==30000
    ledger.action('start','Asia/Shanghai','start-1')
    assert not ledger.state()['running']
    checks.append('Pause stops accrual; idempotent retry cannot restart a paused run')
    reopened=module.Ledger(db);assert reopened.state()['summary']['totalMs']==30000
    checks.append('SQLite records survive service restart')
    module.now_ms=lambda:millis('2026-10-14T16:02:00+00:00')
    reopened.action('start','Asia/Shanghai','start-2')
    module.now_ms=lambda:millis('2026-10-14T16:03:00+00:00')
    assert reopened.state()['summary']['totalMs']==90000
    checks.append('Resuming adds a separate non-overlapping run')
    try:reopened.action('start','BAD/ZONE','bad-zone')
    except ValueError:pass
    else:raise AssertionError('Invalid zone accepted')
    checks.append('Invalid time zones are rejected')
    spring=module.split_days(millis('2026-03-08T00:00:00-05:00'),millis('2026-03-09T00:00:00-04:00'),'America/New_York')
    fall=module.split_days(millis('2026-11-01T00:00:00-04:00'),millis('2026-11-02T00:00:00-05:00'),'America/New_York')
    assert spring=={'2026-03-08':23*3600000};assert fall=={'2026-11-01':25*3600000}
    checks.append('DST days retain their real 23-hour / 25-hour durations')

print(json.dumps({'checks':checks,'errors':[]},ensure_ascii=False))
(root/'output/时间银行后台验证.json').write_text(json.dumps({'checks':checks,'errors':[]},ensure_ascii=False,indent=2),encoding='utf-8')
