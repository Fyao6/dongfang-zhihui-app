from pathlib import Path
p=Path(__file__).resolve().parent
s=(p/'公网适配全量回归.cjs').read_text(encoding='utf-8')
s=s.replace('127.0.0.1:8877','127.0.0.1:8878').replace('公网适配全量回归结果','Netlify适配全量回归结果').replace('公网适配接口实测证据','Netlify适配接口实测证据').replace('公网-','Netlify-')
s=s.replace("'当前全部已实现模块'","'Netlify完整前后台适配'")
s=s.replace("'dist/server/index.js'","'worker/netlify-api.js','netlify.toml','prepare-netlify.mjs'")
(p/'Netlify适配全量回归.cjs').write_text(s,encoding='utf-8')
print('Netlify full integration regression prepared.')
