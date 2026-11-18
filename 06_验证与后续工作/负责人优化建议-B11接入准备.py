"""B11 build-list integration, prepared only. Default is read-only; --apply writes only existing build.py.
Does not run a build, a service, a database, a release or any JavaScript.
"""
from pathlib import Path
import argparse
import hashlib
import json

ROOT = Path(__file__).resolve().parents[1]
R4 = ROOT / "04_研发源码" / "app" / "r4"
EXPECTED = {
  "life-chart-core.js": "479c167019485948e57149b8ecad5d10a055366869a7c652694ac3d8416f763c",
  "life-chart-bazi.js": "81903f5a470c20b43e183e71072de4cb73d77868a907fc39b288c61a3bb6b9b5",
  "bazi-time.js": "3ae3d968e83deddb3f39d274c42a7ebdfd5db3b7ff6873464b09e539184cd23c",
  "life-birth-entry.js": "5aacca949848d665408d41f2f6496202642822012ade3070475039cc0cddf97a",
  "vendor/lunar-1.7.7.js": "9750324bfe1aa63c146f8c72b1143df924466c11c8a5277d7d9225c541a18aaa"
}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Explicitly update only the existing build.py lists; no build is run")
    args = parser.parse_args()
    for name, expected in EXPECTED.items():
        if hashlib.sha256((R4 / name).read_bytes()).hexdigest() != expected:
            raise SystemExit("Frozen implementation source changed; review and freeze a new release manifest before integration: " + name)
    for name in ["bazi-result-version.js", "bazi-result-version-ui.js", "bazi-result-version.css", "bazi-result-version-release.js"]:
        if not (R4 / name).is_file():
            raise SystemExit("Missing prepared helper: " + name)
    target = R4 / "build.py"
    old = target.read_text(encoding="utf-8")
    mutations = [
        ("'life-chart-bazi.css',", "'life-chart-bazi.css','bazi-result-version.css',"),
        ("'life-western-profile.js',", "'life-western-profile.js','bazi-result-version.js','bazi-result-version-ui.js',"),
        ("'i18n-ui.js'])", "'i18n-ui.js','bazi-result-version-release.js'])"),
    ]
    states = [after in old for before, after in mutations]
    if any(states) and not all(states):
        raise SystemExit("Partial integration detected; resolve it explicitly before continuing")
    new = old
    if not all(states):
        for before, after in mutations:
            if new.count(before) != 1:
                raise SystemExit("Expected unique build anchor missing or ambiguous: " + before)
            new = new.replace(before, after, 1)
    report = {"mode": "apply" if args.apply else "dry-run", "target": str(target.relative_to(ROOT)), "wouldChange": new != old,
        "sourceHashesVerified": True, "teacherConfirmed": False, "coreChanges": False, "buildExecuted": False, "serviceStarted": False}
    if args.apply and new != old:
        target.write_text(new, encoding="utf-8", newline="")
    print(json.dumps(report, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()

