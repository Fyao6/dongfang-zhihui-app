"""Read-only checks for the current delivery manifest, embedded build and requirements."""
import csv
import hashlib
import json
from pathlib import Path
import sys
from urllib.parse import unquote, urlsplit
from lxml import html

sys.stdout.reconfigure(encoding='utf-8')
root = Path(__file__).resolve().parent.parent
source = root / '04_研发源码/app/r4'
web = root / '03_当前APP'
checks = []

def checked(name, fn):
    fn()
    checks.append(name)

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def manifest_check():
    manifest = json.loads((root / '原始来源与文件校验.json').read_text(encoding='utf-8'))['files']
    csv_rows = list(csv.DictReader((root / '资料校验清单.csv').open(encoding='utf-8-sig')))
    assert len(manifest) == len(csv_rows)
    for item, row in zip(manifest, csv_rows):
        file = root / item['path']
        assert file.is_file(), item['path']
        assert file.stat().st_size == item['bytes'] == int(row['字节数']), item['path']
        assert digest(file) == item['sha256'] == row['SHA-256'], item['path']
        assert item['path'] == row['包内相对位置']
    expected = {p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file() and not any(part in ('.git','__pycache__') for part in p.parts) and not any(x in p.name for x in ('.sqlite3','.pyc')) and p.name not in ('资料校验清单.csv','原始来源与文件校验.json')}
    assert expected == {item['path'] for item in manifest}, 'Files missing from current manifest'

def build_check():
    app = (web / '东方智慧-首页体验R4.html').read_text(encoding='utf-8')
    review = (web / '发给负责人-东方智慧首页R4.html').read_text(encoding='utf-8')
    embedded, _ = json.JSONDecoder().raw_decode(review.split('const APP=', 1)[1])
    assert embedded.replace('__INITIAL__','{}') == app, 'Review app differs from standalone app'
    for name in ('platform.js','platform.css','time-bank.js'):
        assert (source / name).read_text(encoding='utf-8') in app, name+' not in current build'
    assert (web / '计时后台-开发联调.html').read_text(encoding='utf-8') == (source / 'time-bank-admin.html').read_text(encoding='utf-8').replace('__SNAPSHOT__','null')
    assert not (source.parent / 'output').exists()
    assert not (root / 'output').exists()

def link_check():
    for name in ('打开这里.html','改动任务表-2026-10-22.html'):
        file = root / name
        doc = html.fromstring(file.read_text(encoding='utf-8'))
        for value in doc.xpath('//@href | //@src'):
            url = urlsplit(value)
            if url.scheme or url.netloc:
                continue
            target = (file.parent / unquote(url.path)).resolve() if url.path else file
            assert target.is_relative_to(root.resolve()), value+' escapes current project'
            assert target.exists(), name+': '+value
            if url.fragment and target.suffix == '.html':
                parsed = html.fromstring(target.read_text(encoding='utf-8'))
                assert parsed.xpath('//*[@id=$anchor]', anchor=unquote(url.fragment)), value+' missing anchor'

def requirements_check():
    audit = json.loads((root / '06_验证与后续工作/1016反馈逐项原文.json').read_text(encoding='utf-8'))
    assert digest(root / audit['document']) == audit['sha256']
    assert digest(root / audit['supplement_image']) == audit['supplement_sha256']
    assert len(audit['media']) == 6
    for media in audit['media']:
        assert digest(root / media['path']) == media['sha256']
    task = html.fromstring((root / '改动任务表-2026-10-22.html').read_text(encoding='utf-8'))
    words = ''.join(task.itertext())
    captions = [item['text'] for item in audit['ordered_paragraphs'] if item['text'].strip()]
    assert len(captions) == 7
    assert all(text in words for text in captions), 'Original feedback missing'
    rows = task.xpath('//table[contains(@class,"task-table")]/tbody/tr')
    assert len(rows) == 28 and len({r.get('id') for r in rows}) == 28
    for row in rows:
        cells = row.xpath('./td')
        assert len(cells) == 5 and cells[0].text == row.get('id'), row.get('id')+' malformed columns'
    states = [row.xpath('.//span[@class="status"]')[0].text for row in rows]
    assert sum('通过本地回归' in state for state in states) == 25
    assert sum('待真实' in state for state in states) == 3
    tracking = json.loads((root / '06_验证与后续工作/需求追踪表.json').read_text(encoding='utf-8'))['current_tasks']
    assert len(tracking) == 28
    assert all(item['module'] == ''.join(row.xpath('./td')[1].itertext()) for item, row in zip(tracking, rows))

def regression_check():
    latest = json.loads((root / '06_验证与后续工作/本轮全量回归结果.json').read_text(encoding='utf-8'))['latest']
    assert latest['pass'] and latest['failed'] == 0
    assert latest['coverage']['adminUi'] and not latest['coverage']['liveAi'] and not latest['coverage']['realHardware']
    for name, expected in latest['buildHashes'].items():
        assert digest(web / name) == expected, name+' differs from the actual regression build'
    assert not list((root / '06_验证与后续工作').glob('本轮回归专用.sqlite3*')), 'Test database not cleaned'

checked('当前JSON与CSV全部文件的SHA-256、大小及覆盖范围', manifest_check)
checked('源码、独立APP、负责人查看页及统一后台一致', build_check)
checked('根目录入口与任务表全部本地链接', link_check)
checked('原始反馈完整性、28项任务及状态表一致', requirements_check)
checked('最新全量回归通过及测试数据清理', regression_check)
print(json.dumps({'pass': True, 'checks': checks}, ensure_ascii=False, indent=2))
