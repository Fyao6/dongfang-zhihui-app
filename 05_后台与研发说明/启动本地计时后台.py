from pathlib import Path
import sys, runpy
base=Path(__file__).resolve().parent.parent
server=base/'04_研发源码/app/r4/backend/server.py'
web=base/'03_当前APP'
sys.argv=[str(server),'--web-root',str(web)]+sys.argv[1:]
runpy.run_path(str(server),run_name='__main__')
