"""Preserve a frozen report and write a separately identified handoff redaction."""
from pathlib import Path
from datetime import datetime, timezone, timedelta
import hashlib
import json
import re

AREA = Path(__file__).resolve().parent
SOURCE = AREA / '负责人优化建议-数字权益专项-python.json'
DEST = AREA / '负责人优化建议-数字权益专项-python-脱敏交接副本.json'
EXPECTED = '2722f5c0467ed1f8bb3b23bdd70a97924f30abcd42dbe931fdb368aabcd8b870'
data = SOURCE.read_bytes()
assert hashlib.sha256(data).hexdigest() == EXPECTED
pattern = re.compile(r'ew_session=[A-Za-z0-9_.-]{16,}')
count = 0
def redact(value):
    global count
    if isinstance(value, str):
        result, n = pattern.subn('ew_session=[REDACTED_SESSION]', value)
        count += n
        return result
    if isinstance(value, list): return [redact(v) for v in value]
    if isinstance(value, dict): return {k: redact(v) for k, v in value.items()}
    return value
document = redact(json.loads(data))
assert count > 0
document['handoffRedaction'] = {
    'source': SOURCE.name, 'sourceSHA256': EXPECTED,
    'redactedSessionOccurrences': count,
    'sourceOriginalRetainedLocally': True,
    'scope': 'Separate redacted handoff copy; original pass/fail evidence is unchanged and is not re-run.'
}
payload = (json.dumps(document, ensure_ascii=False, indent=2) + '\n').encode('utf-8')
assert not pattern.search(payload.decode())
if DEST.exists(): assert DEST.read_bytes() == payload
else: DEST.write_bytes(payload)
assert SOURCE.read_bytes() == data
record = {'atBeijing': datetime.now(timezone(timedelta(hours=8))).isoformat(),
    'source': '06_验证与后续工作/' + SOURCE.name, 'sourceSHA256': EXPECTED,
    'sourceExcludedFromZIPAndGit': True, 'sourceOriginalPreserved': True,
    'copy': '06_验证与后续工作/' + DEST.name,
    'copySHA256': hashlib.sha256(payload).hexdigest(),
    'redactedOccurrences': count, 'secretValuesPrinted': False}
(AREA / '项目交付-报告脱敏记录.json').write_bytes((json.dumps(record, ensure_ascii=False, indent=2) + '\n').encode())
print(json.dumps(record, ensure_ascii=False))
