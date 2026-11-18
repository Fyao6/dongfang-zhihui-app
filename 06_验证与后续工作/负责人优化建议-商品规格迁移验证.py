"""Run on fresh SQLite and isolated local D1 only. No preview DB access."""
import argparse
import json
import re
import sqlite3
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACK = ROOT / '04_研发源码/app/r4/backend'
sys.path.insert(0, str(BACK))
import commerce

LEGACY_DDL = commerce.DDL.replace(
    'product_id TEXT NOT NULL REFERENCES commerce_products(id),sku',
    'product_id TEXT NOT NULL UNIQUE REFERENCES commerce_products(id),sku',
)
SEED = """
INSERT INTO commerce_products VALUES('old-product','原商品','','physical','sandbox','published',1,'','["CN"]',0,0,'original',1,1,'{}');
INSERT INTO commerce_skus VALUES('original-sku','old-product','ORIGINAL','sandbox',100,'CNY',6,0,1);
INSERT INTO commerce_prices VALUES('original-price','original-sku',1,100,'CNY',1);
INSERT INTO commerce_orders VALUES('original-order','synthetic','sandbox','original','fingerprint','awaiting_payment','unpaid','awaiting_payment','none','CNY',200,0,0,200,0,'{}','{}',4102444800000,1,1);
INSERT INTO commerce_order_items VALUES('original-item','original-order','original-sku','old-product','原商品','physical',2,100,'CNY',0,0,'',1,0,'{}');
INSERT INTO commerce_reservations VALUES('original-order','original-sku',2,'held');
"""
QUERY = """
SELECT
 (SELECT reserved FROM commerce_skus WHERE id='original-sku') AS reserved,
 (SELECT price_minor FROM commerce_prices WHERE id='original-price') AS price,
 (SELECT sku_id FROM commerce_order_items WHERE id='original-item') AS itemSku,
 (SELECT state FROM commerce_reservations WHERE order_id='original-order') AS reservation,
 (SELECT count(*) FROM pragma_foreign_key_check WHERE parent='commerce_skus') AS brokenReferences,
 (SELECT count(*) FROM sqlite_master WHERE name IN ('commerce_reserve_release','commerce_reserve_check')) AS triggers
"""


def prepare_d1(state):
    assert re.fullmatch(r'variant-migration-[a-f0-9]{32}', state.name)
    assert state.parent == Path(__file__).resolve().parent and state.is_dir()
    return [str(Path(sys.executable).parent / 'node.exe') if (Path(sys.executable).parent / 'node.exe').is_file() else 'node',
            str(ROOT / '04_研发源码/app/cloud/node_modules/wrangler/bin/wrangler.js'),
            'd1', 'execute', 'DB', '--local', '--persist-to', str(state),
            '--config', str(ROOT / '04_研发源码/app/cloud/dist/server/wrangler.json'), '--json']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--d1-state', type=Path)
    parser.add_argument('--seed', action='store_true')
    args = parser.parse_args()
    if args.d1_state:
        command = prepare_d1(args.d1_state.resolve())
        if args.seed:
            sql = LEGACY_DDL + SEED + "INSERT INTO settings VALUES('commerce_schema_v1','true');"
            # No external source or account. These rows live only in the dedicated migration fixture.
            subprocess.run([*command, '--command', sql], check=True, capture_output=True)
            return
        query = QUERY + "; SELECT sql FROM sqlite_master WHERE name='commerce_skus';"
        batches = json.loads(subprocess.check_output([*command, '--command', query], encoding='utf-8'))
        row, schema = (batch['results'][0] for batch in batches)
        assert 'product_id TEXT NOT NULL UNIQUE REFERENCES' not in schema['sql']
        target = 'cloud'
    else:
        assert not args.seed
        with sqlite3.connect(':memory:') as db:
            db.row_factory = sqlite3.Row
            db.execute('PRAGMA foreign_keys=ON')
            db.executescript(LEGACY_DDL + SEED)
            for _ in range(2):
                commerce.init_schema(db)
                db.commit()
            row = dict(db.execute(QUERY).fetchone())
            db.execute("INSERT INTO commerce_skus VALUES('new-sku','old-product','NEW','sandbox',200,'CNY',4,0,2)")
            assert db.execute("SELECT count(*) FROM commerce_skus WHERE product_id='old-product'").fetchone()[0] == 2
        target = 'python'
    assert row == {'reserved': 2, 'price': 100, 'itemSku': 'original-sku', 'reservation': 'held',
                   'brokenReferences': 0, 'triggers': 2}, row
    print(json.dumps({'target': target, 'pass': True, 'syntheticOnly': True, 'preserved': row}, ensure_ascii=False))


if __name__ == '__main__':
    main()
