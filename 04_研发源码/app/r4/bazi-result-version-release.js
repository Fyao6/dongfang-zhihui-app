// Frozen implementation manifest for B11. This is not teacher approval.
// This file is not in the current build. Load it last only after explicit integration.
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
  root.BAZI_RELEASE_MANIFEST = Object.freeze({...manifest, engine: Object.freeze({...manifest.engine}), sourceHashes: Object.freeze(sourceHashes)});
  root.BaziVersionUI.install({manifest: root.BAZI_RELEASE_MANIFEST});
})(typeof globalThis === 'object' ? globalThis : this);

