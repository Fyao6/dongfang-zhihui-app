from pathlib import Path
# Preserve the first frozen build and bind the repaired current build separately.
script=(Path(__file__).with_name('成长统计-冻结构建.py')).read_text(encoding='utf-8')
script=script.replace("target=root/'06_验证与后续工作/成长统计-稳定构建记录.json'", "target=root/'06_验证与后续工作/成长统计-兼容修复后稳定构建记录.json'")
script=script.replace("'04_研发源码/app/r4/growth-tree.css'],'builds'", "'04_研发源码/app/r4/growth-tree.css','04_研发源码/app/r4/daily.js','04_研发源码/app/r4/homepage.js','04_研发源码/app/r4/journey.js'],'builds'")
exec(compile(script,__file__,'exec'))
