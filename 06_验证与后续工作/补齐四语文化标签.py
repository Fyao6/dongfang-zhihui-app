
from pathlib import Path
p=Path(__file__).resolve().parent.parent
r=p/'04_研发源码/app/r4'
f=r/'platform.js';s=f.read_text(encoding='utf-8')
for en,zh in [('A MOMENT FOR YOURSELF','留给自己的片刻'),('RETURN TO THIS MOMENT','回到此刻')]:s=s.replace('>'+en+'</span>','>'+chr(36)+'{t("'+en+'","'+zh+'")}</span>')
f.write_text(s,encoding='utf-8')
f=r/'life.js';s=f.read_text(encoding='utf-8')
s=s.replace("['en','bo'].includes(state.lang)?window.iztro.astro.bySolar(profile.solarDate,Number(profile.timeIndex),profile.gender,true,'en-US'):base","window.iztro.astro.bySolar(profile.solarDate,Number(profile.timeIndex),profile.gender,true,'en-US')")
f.write_text(s,encoding='utf-8')

