"""Reproduce the offline GeoNames snapshot from pinned local official files only."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import re
import subprocess
import sys
import zipfile
from zoneinfo import available_timezones

ROOT = Path(__file__).resolve().parent.parent
VENDOR = ROOT / '04_研发源码/app/r4/vendor'
OUTPUT = '04_研发源码/app/r4/life-western-cities.js'
RECORD = '02_需求与设计参考/出生城市离线索引来源-20261111.json'
VERSION = 'geonames-cities15000-2026-11-11'
PINNED = {
    'cities15000.zip': ('geonames-cities15000-20261111.zip', '2bbf3f840aa5dcc7704e2b72e37146f0a4c939191a1ccbf4199f6b8c4041f29f'),
    'admin1CodesASCII.txt': ('geonames-admin1CodesASCII-20261111.txt', '2e4867f5397acb056ea26377601b57af37cb4c81399770225018e9e439e91ad3'),
    'countryInfo.txt': ('geonames-countryInfo-20261111.txt', '79f8f59ea01cbb40438bf1856dd6c2ff201f03f8fc72d0530b2646aaf603ef04'),
    'readme.txt': ('geonames-readme-20261111.txt', 'b1957379b6c1242c700c98ac9a8aa0a09f56c3c0a50ee72175527005f48ef2c5'),
    'timeZones.txt': ('geonames-timeZones-20261111.txt', 'efa95af085ea8a6d41f876c64649f6e38feda01b1e6f612d5765067f50114de2'),
}
COLUMNS = ['id', 'name', 'ascii', 'country', 'admin1', 'lat', 'lon', 'tz', 'population', 'aliases']
EXPECTED = {
    1816670: ('Beijing', 'Asia/Shanghai'), 1796236: ('Shanghai', 'Asia/Shanghai'),
    5128581: ('New York City', 'America/New_York'), 2988507: ('Paris', 'Europe/Paris'),
    2643743: ('London', 'Europe/London'), 1819729: ('Hong Kong', 'Asia/Hong_Kong'),
    1280737: ('Lhasa', 'Asia/Shanghai'), 1275004: ('Kolkata', 'Asia/Kolkata'),
}

def need(ok, message):
    if not ok:
        raise AssertionError(message)

def sha(data):
    return hashlib.sha256(data).hexdigest()

def main():
    sys.stdout.reconfigure(encoding='utf-8')
    sources, raw = {}, {}
    for remote, (filename, expected) in PINNED.items():
        path = VENDOR / filename
        data = path.read_bytes()
        need(sha(data) == expected, 'Pinned official snapshot changed: ' + filename)
        raw[remote] = data
        sources[path.relative_to(ROOT).as_posix()] = {'url': 'https://download.geonames.org/export/dump/' + remote, 'bytes': len(data), 'sha256': expected}
    with zipfile.ZipFile(VENDOR / PINNED['cities15000.zip'][0]) as archive:
        member = archive.getinfo('cities15000.txt')
        extracted = archive.read(member)
        need(archive.testzip() is None, 'Official raw ZIP CRC failed')
        archive_date = '%04d-%02d-%02dT%02d:%02d:%02d' % member.date_time
    fields = [line.split('\t') for line in extracted.decode('utf-8').splitlines() if line]
    need(len(fields) == 34214 and all(len(row) == 19 for row in fields), 'Snapshot row count/shape changed')
    countries = {}
    for line in raw['countryInfo.txt'].decode('utf-8').splitlines():
        if line and not line.startswith('#'):
            row = line.split('\t')
            countries[row[0]] = row[4]
    admin1 = {}
    for line in raw['admin1CodesASCII.txt'].decode('utf-8').splitlines():
        if line:
            row = line.split('\t')
            admin1[row[0]] = row[1]
    rows = [[int(row[0]), row[1], row[2], row[8], row[10], float(row[4]), float(row[5]), row[17], int(row[14]), row[3]] for row in fields]
    need(len({row[0] for row in rows}) == len(rows), 'Duplicate GeoNames id')
    zones = sorted({row[7] for row in rows})
    need(set(zones) <= available_timezones(), 'Unknown IANA zone in snapshot')
    for row in rows:
        need(row[1] and row[2] and row[3] in countries and -90 <= row[5] <= 90 and -180 <= row[6] <= 180 and row[8] >= 0, 'Invalid city fields')
    intl_check = "const z=JSON.parse(require('fs').readFileSync(0,'utf8'));for(const s of z)new Intl.DateTimeFormat('en',{timeZone:s}).format(0);console.log(z.length)"
    checked = subprocess.run(['node', '-e', intl_check], input=json.dumps(zones), text=True, capture_output=True, encoding='utf-8')
    need(checked.returncode == 0 and checked.stdout.strip() == str(len(zones)), 'Native JavaScript Intl timezone validation failed')
    rows.sort(key=lambda row: (-row[8], row[0]))
    by_id = {row[0]: row for row in rows}
    probes = {}
    for city_id, (name, zone) in EXPECTED.items():
        row = by_id[city_id]
        need(row[1] == name and row[7] == zone, 'Known city identity changed')
        probes[str(city_id)] = dict(zip(COLUMNS[:9], row[:9]))
    coverage = {'cities': len(rows), 'countryCodes': len({row[3] for row in rows}), 'chinaCities': sum(row[3] == 'CN' for row in rows), 'citiesWithHanAliases': sum(bool(re.search('[\u3400-\u9fff]', row[9])) for row in rows), 'timeZones': len(zones)}
    snapshot = {'version': VERSION, 'rawSha256': PINNED['cities15000.zip'][1], 'archiveDate': archive_date, 'archiveTimeZone': 'unspecified ZIP local timestamp'}
    source = {'name': 'GeoNames', 'dataset': 'cities15000', 'url': 'https://download.geonames.org/export/dump/cities15000.zip', 'license': 'CC BY 4.0', 'licenseUrl': 'https://creativecommons.org/licenses/by/4.0/', 'attributionUrl': 'https://www.geonames.org/'}
    data = {'schemaVersion': 1, 'source': source, 'snapshot': snapshot, 'columns': COLUMNS, 'coverage': coverage, 'sort': 'population descending, id ascending', 'countries': countries, 'admin1': admin1, 'rows': rows}
    serialized = json.dumps(data, ensure_ascii=False, separators=(',', ':')).replace('<', '\\u003c').replace('>', '\\u003e').replace('\u2028', '\\u2028').replace('\u2029', '\\u2029')
    script = '// GeoNames cities15000, ' + VERSION + '. CC BY 4.0; https://www.geonames.org/; https://creativecommons.org/licenses/by/4.0/\n// Modified: selected fields, numeric coordinates/population, tuple encoding and population order. All source aliases retained. No inferred translation or coordinate/timezone override.\nglobalThis.LC_CITY_DATA=' + serialized + ';\n'
    syntax = subprocess.run(['node', '--check', '-'], input=script, text=True, capture_output=True, encoding='utf-8')
    need(syntax.returncode == 0, 'Generated JavaScript syntax failed: ' + syntax.stderr)
    notice = '''GeoNames offline city index
Creator/data source: GeoNames — https://www.geonames.org/
Data download: https://download.geonames.org/export/dump/
License: Creative Commons Attribution 4.0 International (CC BY 4.0)
License link: https://creativecommons.org/licenses/by/4.0/
Legal code: https://creativecommons.org/licenses/by/4.0/legalcode
Snapshot: ''' + VERSION + '''

Adaptation by this APP: selected official fields; numeric coordinates and population;
compact tuple encoding; population order; official country/admin names included.
All city name/asciiname/alternatenames values are retained from the pinned snapshot.
No invented translation, time-zone override, coordinate override or city prediction.
GeoNames does not endorse this APP. The source data is supplied "as is", without
warranty of accuracy, timeliness or completeness; see the source readme.
The GeoNames data remains under CC BY 4.0. This notice does not change licenses
of the APP code or the other bundled dependencies.

Coverage is cities15000 (population >15,000 or capitals), not every village,
street, hospital or historical city. Coordinates represent the named place,
not an exact birth address. A matching candidate must be explicitly selected.
Unknown cities must fail; do not substitute a guessed city/zone/coordinate.
Aliases are multilingual without language labels. In particular New York City
contains traditional Chinese 紐約/紐約市; simplified/traditional query conversion
must use the existing OpenCC data and must not misidentify nearby East Meadow.
Identical names require country/admin/id disambiguation. Candidate search is
local; no online geocoder, autocomplete API, key or account is included.

Pinned raw download hashes and transformation details:
02_需求与设计参考/出生城市离线索引来源-20261111.json
'''
    need('Creative Commons Attribution 4.0' in raw['readme.txt'].decode('utf-8'), 'Source license statement absent')
    source_record = {'checked_utc': datetime.now(timezone.utc).isoformat(), 'snapshot': snapshot, 'official_sources': sources, 'official_schema_url': 'https://download.geonames.org/export/dump/readme.txt', 'license_url': source['licenseUrl'], 'coverage': coverage, 'columns': COLUMNS, 'output': {'path': OUTPUT, 'bytes': len(script.encode('utf-8')), 'sha256': sha(script.encode('utf-8'))}, 'notice': {'path': '04_研发源码/app/r4/vendor/geonames-LICENSE-NOTICE.txt', 'sha256': sha(notice.encode('utf-8'))}, 'extracted_text': {'bytes': len(extracted), 'sha256': sha(extracted)}, 'known_city_checks': probes, 'validations': {'unique_ids': True, 'python_iana_timezones': len(zones), 'javascript_intl_timezones': len(zones), 'raw_zip_crc': True, 'javascript_syntax': True}, 'modifications': ['Selected official id/name/asciiname/country/admin1/latitude/longitude/timezone/population/alternatenames fields.', 'Converted numeric fields to numbers and sorted by population descending/id ascending.', 'Kept all original aliases; did not infer language, translate labels or override coordinates/timezones.'], 'search_boundary': ['Use existing OpenCC for simplified/traditional Chinese equivalence; New York City has 紐約 but not 纽约 in raw aliases.', 'Normalize diacritics/case/spacing for actual ascii/pinyin/aliases; do not invent translations.', 'Return at most 50 explicit country/admin-disambiguated candidates; not found means fail, never guess.'], 'limits': ['City coverage does not include all villages, streets or hospitals.', 'Representative place coordinates are not an exact birth address.', 'The source timezone ID is retained (including Asia/Urumqi); historic civil-time offsets are resolved by the APP runtime, not fixed numeric offsets in this index.', 'Source data as-is; this is a data/index validation, not W1 APP acceptance or production deployment.', 'Raw ZIP is retained locally but excluded from delivery payload by the existing archive filter.']}
    (ROOT / OUTPUT).write_text(script, encoding='utf-8', newline='\n')
    (VENDOR / 'geonames-LICENSE-NOTICE.txt').write_text(notice, encoding='utf-8', newline='\n')
    (ROOT / RECORD).write_text(json.dumps(source_record, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'pass': True, 'output': source_record['output'], 'snapshot': snapshot, 'coverage': coverage, 'probes': probes}, ensure_ascii=False))

if __name__ == '__main__':
    main()
