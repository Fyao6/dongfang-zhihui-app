"""Deterministic ledger/persistence/Responses-adapter checks. No external AI calls."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import importlib.util
import hashlib
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.stdout.reconfigure(encoding='utf-8')
root = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location('wisdom_server', root / '04_研发源码/app/r4/backend/server.py')
app = importlib.util.module_from_spec(spec)
spec.loader.exec_module(app)
database = Path(__file__).with_name('本轮单元回归专用.sqlite3')


class BackendRegression(unittest.TestCase):
    def setUp(self):
        self.clean()

    def tearDown(self):
        self.clean()

    def clean(self):
        for suffix in ('', '-wal', '-shm'):
            target = Path(str(database) + suffix)
            self.assertEqual(target.parent, Path(__file__).resolve().parent)
            target.unlink(missing_ok=True)

    def test_cross_midnight(self):
        start = int(datetime(2026, 10, 22, 15, 59, 30, tzinfo=timezone.utc).timestamp() * 1000)
        self.assertEqual(app.split_days(start, start + 60000, 'Asia/Shanghai'), {'2026-10-22': 30000, '2026-10-23': 30000})

    def test_restart_preserves_content(self):
        store = app.Store(database)
        with store.connect() as db:
            row = db.execute("SELECT * FROM contents WHERE kind='cards' LIMIT 1").fetchone()
            item = json.loads(row['data'])
            item['zh'] = '保存后的真实配置'
            db.execute("UPDATE contents SET data=? WHERE kind='cards' AND id=?", (app.dump(item), item['id']))
        reopened = app.Store(database)
        self.assertTrue(any(x['zh'] == '保存后的真实配置' for x in reopened.public_content()['cards']))

    def test_concurrent_tabs_count_once(self):
        store = app.Store(database)
        with ThreadPoolExecutor(max_workers=8) as pool:
            states = list(pool.map(lambda _: store.ledger('same-user', 'Asia/Shanghai', True), range(20)))
        self.assertEqual({len(state['runs']) for state in states}, {1})
        self.assertEqual(len({state['runs'][0]['id'] for state in states}), 1)

    def test_closed_session_does_not_backfill(self):
        store = app.Store(database)
        with patch.object(app, 'now_ms', return_value=100000):
            store.ledger('same-user', 'UTC', True)
        with patch.object(app, 'now_ms', return_value=110000):
            store.ledger('same-user', 'UTC', True)
        with patch.object(app, 'now_ms', return_value=220000):
            state = store.ledger('same-user', 'UTC', True)
        self.assertEqual(state['summary']['totalMs'], 10000)
        self.assertEqual(len(state['runs']), 2)
        self.assertEqual(state['runs'][0]['end'], 110000)

    def test_responses_adapter_with_reasoning_item(self):
        fixture_store=app.Store(database)
        unit_token='synthetic-unit-session-token'
        with fixture_store.connect() as db:
            db.execute('INSERT INTO users VALUES(?,?,?,?,?,?)',('unit-test-user','unit_test_user',app.password_hash('synthetic-unit-password'),'Synthetic unit user','user',app.now_ms()))
            db.execute('INSERT INTO sessions VALUES(?,?,?)',(hashlib.sha256(unit_token.encode()).hexdigest(),'unit-test-user',app.now_ms()+60000))
        class Configuration:
            def connect(self):
                return fixture_store.connect()
            def setting(self, _):
                return {'enabled': True, 'apiKeyRef': 'EW_AI_UNIT_TEST', 'model': 'configured-model', 'endpoint': 'https://api.openai.com/v1/responses', 'prompt': '简洁回答', 'knowledge': ''}
        class Response:
            def __enter__(self):
                return self
            def __exit__(self, *_):
                pass
            def read(self, _):
                return app.dump({'output': [{'type': 'reasoning', 'summary': []}, {'type': 'message', 'content': [{'type': 'output_text', 'text': '这是接口适配测试响应。'}]}]}).encode()
        handler_class = app.make_handler(Configuration(), root / '03_当前APP')
        handler = handler_class.__new__(handler_class)
        handler.user = {'id': 'unit-test-user', 'role': 'user'}
        handler.session_token=unit_token
        handler.visitor='0'*32
        handler.owner='unit-test-user'
        handler.cookies_out=[]
        with patch.dict('os.environ', {'EW_AI_UNIT_TEST': 'unit-test-only'}, clear=False), patch.object(app, 'open_legacy_ai', return_value=Response()) as network, patch.object(app, 'privacy_authorize_ai', return_value=None), patch.object(app, 'guarded_legacy_save', return_value=False) as storage, patch.object(app, 'Privacy') as gate:
            gate.return_value.response.return_value = {'policyAcknowledged': True, 'consentEpoch': 'unit-receipt'}
            result = handler.ai_chat({'messages': [{'role': 'user', 'content': '你好', 'privacy': {'consentEpoch': 'unit-receipt'}}]})
        self.assertEqual(result['text'], '这是接口适配测试响应。')
        storage.assert_called_once()
        self.assertEqual(storage.call_args.args[1], 'unit-test-user')
        sent = json.loads(network.call_args.args[0].data)
        self.assertFalse(sent['store'])
        self.assertEqual(network.call_args.args[0].get_header('Authorization'), 'Bearer unit-test-only')
        self.assertEqual(sent['input'][0]['role'], 'user')


if __name__ == '__main__':
    unittest.main(verbosity=2)
