"""Actual managed-source identity for the sample adapter, independent of APP self hash."""
from pathlib import Path
import argparse
import hashlib
import json

R4=Path(__file__).resolve().parent
PROJECT=R4.parents[2]
TARGET=R4/'bazi-sample-source-manifest.json'
MANAGED=(
 '04_研发源码/app/r4/bazi-sample-engine.js',
 '04_研发源码/app/r4/bazi-sample-engine.d.ts',
 '04_研发源码/app/r4/bazi-sample-bridge.js',
 '04_研发源码/app/r4/bazi-samples-ui.js',
 '04_研发源码/app/r4/life-chart-core.js',
 '04_研发源码/app/r4/life-chart-bazi.js',
 '04_研发源码/app/r4/bazi-time.js',
 '04_研发源码/app/r4/bazi-compare.js',
 '04_研发源码/app/r4/life-chart-bazi-annotations.js',
 '04_研发源码/app/r4/life-chart-bazi-layout.js',
 '04_研发源码/app/r4/life-birth-entry.js',
 '04_研发源码/app/r4/bazi-result-version.js',
 '04_研发源码/app/r4/bazi-result-version-ui.js',
 '04_研发源码/app/r4/bazi-result-version-release.js',
 '04_研发源码/app/r4/bazi-interpretation-bridge.js',
 '04_研发源码/app/r4/backend/bazi_sample_worker.cjs',
 '04_研发源码/app/r4/vendor/lunar-1.7.7.js',
 '04_研发源码/app/r4/vendor/lunar-1.7.7-LICENSE.txt',
 '04_研发源码/app/r4/build_bazi_sample_manifest.py',
 '04_研发源码/app/r4/build.py',
 '04_研发源码/app/cloud/prepare.py',
)
PINNED={
 '04_研发源码/app/r4/vendor/lunar-1.7.7.js':'9750324bfe1aa63c146f8c72b1143df924466c11c8a5277d7d9225c541a18aaa',
 '04_研发源码/app/r4/vendor/lunar-1.7.7-LICENSE.txt':'d9210caf1844dcf410095cea464b79800aad30dbd49df092076b9f0ddc015404',
}
sha=lambda value:hashlib.sha256(value).hexdigest()
canonical=lambda value:json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode('utf-8')


def collect(strict=True):
    files={};missing=[]
    for name in sorted(MANAGED):
        path=PROJECT/name
        if not path.is_file():missing.append(name);continue
        digest=sha(path.read_bytes())
        if name in PINNED and digest!=PINNED[name]:raise RuntimeError('Pinned calendar vendor bytes changed: '+name)
        files[name]=digest
    if strict and missing:raise RuntimeError('Bazi sample sources are incomplete: '+', '.join(missing))
    core={'schema':1,'kind':'bazi-sample-managed-source','engine':{'name':'lunar-javascript','version':'1.7.7','license':'MIT','vendorSHA256':PINNED['04_研发源码/app/r4/vendor/lunar-1.7.7.js']},
          'implementationReady':not missing,'sourceHashes':files,'missingSources':missing,'professionalValidation':False,'teacherConfirmed':False}
    return {**core,'manifestSha256':sha(canonical(core))}


def encoded(value):return (json.dumps(value,ensure_ascii=False,indent=2)+'\n').encode('utf-8')


def write_manifest(strict=True):
    value=collect(strict)
    TARGET.write_bytes(encoded(value))
    return value


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--allow-incomplete',action='store_true',help='Component readiness only; new runs must remain blocked.')
    parser.add_argument('--cloud-descriptor',action='store_true',help='Also record the currently served Cloud APP, without a self-hash cycle.')
    args=parser.parse_args();value=write_manifest(not args.allow_incomplete)
    if args.cloud_descriptor:
        app=PROJECT/'04_研发源码/app/cloud/generated/experience.html'
        descriptor={'schema':1,'sourceManifest':value,'sourceManifestSha256':value['manifestSha256'],'appSha256':sha(app.read_bytes()) if app.is_file() else None,
                    'servedPath':'/experience','implementationReady':False,'readinessReason':'component_descriptor_requires_full_build_prepare'}
        (PROJECT/'04_研发源码/app/cloud/generated/bazi-sample-server-manifest.json').write_bytes(encoded(descriptor))
    print(json.dumps({'implementationReady':value['implementationReady'],'sources':len(value['sourceHashes']),'missing':value['missingSources'],'manifestSha256':value['manifestSha256']},ensure_ascii=True))
