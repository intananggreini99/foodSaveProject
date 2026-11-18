"""Pastikan tidak ada kode awal tim yang dihapus atau diganti."""
from pathlib import Path
import ast
import json
import subprocess

ROOT=Path(__file__).resolve().parents[1]
REFERENCE='06eb640b8183ba855ed67a712ad25d87cfaacf5c'
checks=[]
for path in sorted((ROOT/'notebooks').glob('*.ipynb')):
    relative=path.relative_to(ROOT).as_posix()
    original=json.loads(subprocess.check_output(['git','show',f'{REFERENCE}:{relative}'],cwd=ROOT))
    current=json.loads(path.read_text(encoding='utf-8'))
    retained=[c for c in current['cells'] if not c.get('metadata',{}).get('foodsave_added')]
    assert len(retained)==len(original['cells']),relative
    for old,now in zip(original['cells'],retained):
        assert old['cell_type']==now['cell_type'] and old['source']==now['source'],relative
    added=[c for c in current['cells'] if c.get('metadata',{}).get('foodsave_added')]
    for cell in added:
        if cell['cell_type']=='code':ast.parse(''.join(cell['source']))
    checks.append({'notebook':relative,'original_cells_unchanged':len(retained),'added_cells':len(added),'syntax':'passed'})
    print(relative,': kode lama utuh;',len(added),'sel tambahan')
out=ROOT/'results/evaluation/notebook_preservation.json'
out.write_text(json.dumps({'reference_commit':REFERENCE,'status':'passed','checks':checks},indent=2),encoding='utf-8')
