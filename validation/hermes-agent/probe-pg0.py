"""Fresh embedded PostgreSQL fixture; no Hindsight API/provider calls."""
from pathlib import Path
import json,sys
from pg0 import Pg0
root=Path('/home/workshop/.hindsight/pg0/sdk-synthetic-probe')
root.mkdir(mode=0o700,parents=True,exist_ok=True)
pg=Pg0(name='sdk-synthetic-probe',port=55432,data_dir=str(root))
try:
    pg.start()
    if '--read-existing' not in sys.argv:
        pg.execute('CREATE TABLE IF NOT EXISTS sdk_probe (id INTEGER PRIMARY KEY, value TEXT NOT NULL);')
        pg.execute("INSERT INTO sdk_probe VALUES (1,'durable') ON CONFLICT (id) DO NOTHING;")
    result=pg.execute('SELECT value FROM sdk_probe WHERE id=1;')
    assert 'durable' in result,result
    print(json.dumps({'embedded_pg0':'0.15.2','state':'durable','query_pass':True,'read_existing':'--read-existing' in sys.argv}),flush=True)
finally:
    pg.stop()
