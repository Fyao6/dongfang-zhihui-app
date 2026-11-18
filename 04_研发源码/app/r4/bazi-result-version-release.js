// Frozen implementation manifest for B11. This is not teacher approval.
// Integrated release: old archives retain their original provenance; new calculations use the managed implementation identity.
(function(root) {
  'use strict';
  const sourceHashes = {
  "life-chart-core.js": "479c167019485948e57149b8ecad5d10a055366869a7c652694ac3d8416f763c",
  "life-chart-bazi.js": "81903f5a470c20b43e183e71072de4cb73d77868a907fc39b288c61a3bb6b9b5",
  "bazi-time.js": "3ae3d968e83deddb3f39d274c42a7ebdfd5db3b7ff6873464b09e539184cd23c",
  "life-birth-entry.js": "5aacca949848d665408d41f2f6496202642822012ade3070475039cc0cddf97a",
  "vendor/lunar-1.7.7.js": "9750324bfe1aa63c146f8c72b1143df924466c11c8a5277d7d9225c541a18aaa"
};
  const manifest = {
  "engine": {
    "name": "lunar-javascript",
    "version": "1.7.7"
  },
  "ruleVersion": "implementation-sha256:69e61f05064b221567e18019a8cf5260d4c7114a722937eb8c6c81e561be472b",
  "adapterVersion": "sha256:81903f5a470c20b43e183e71072de4cb73d77868a907fc39b288c61a3bb6b9b5",
  "teacherConfirmed": false
};
  const descriptor=root.BAZI_SAMPLE_SOURCE_MANIFEST;
  const ready=descriptor?.implementationReady===true&&/^[a-f0-9]{64}$/.test(descriptor.manifestSha256||'')&&/^[a-f0-9]{64}$/.test(descriptor.sourceHashes?.['04_研发源码/app/r4/bazi-sample-engine.js']||'');
  const current=descriptor?{...manifest,ruleVersion:ready?'implementation-sha256:'+descriptor.manifestSha256:'implementation-unavailable',adapterVersion:ready?'sha256:'+descriptor.sourceHashes['04_研发源码/app/r4/bazi-sample-engine.js']:'unavailable',teacherConfirmed:false}:manifest;
  const hashes=descriptor?descriptor.sourceHashes:sourceHashes;
  root.BAZI_RELEASE_MANIFEST=Object.freeze({...current,engine:Object.freeze({...current.engine}),sourceHashes:Object.freeze({...hashes}),...(descriptor?{implementationReady:ready}:{})});
  root.BaziVersionUI.install({manifest:root.BAZI_RELEASE_MANIFEST});
})(typeof globalThis === 'object' ? globalThis : this);

