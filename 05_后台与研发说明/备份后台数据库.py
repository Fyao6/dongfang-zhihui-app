"""SQLite consistent online backup; no deletion or restoration."""
from pathlib import Path
from datetime import datetime, timezone, timedelta
import sqlite3
import sys
sys.stdout.reconfigure(encoding='utf-8')
root=Path(__file__).resolve().parent.parent
source=root/'04_研发源码/app/r4/backend/eastern-wisdom.sqlite3'
folder=root/'07_历史版本仅供追溯'
if not source.is_file() or not folder.is_dir():
 raise SystemExit('未找到正式数据库或现有历史目录；未执行备份。')
stamp=datetime.now(timezone(timedelta(hours=8))).strftime('%Y%m%d-%H%M%S-%f')
target=folder/('后台数据库备份-'+stamp+'.sqlite3')
with sqlite3.connect(source.as_uri()+'?mode=ro',uri=True) as src, sqlite3.connect(target) as dest:
 src.backup(dest)
 if dest.execute('PRAGMA integrity_check').fetchone()[0]!='ok':
  raise SystemExit('备份完整性检查失败，请保留现场核查。')
print('备份完成，完整性检查通过：'+str(target))
