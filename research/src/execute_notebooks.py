"""Eksekusi notebook menggunakan kernel proyek dan simpan output di file asli."""
import os
import sys
from pathlib import Path
import nbformat
from nbclient import NotebookClient
from jupyter_client.kernelspec import KernelSpecManager

ROOT=Path(__file__).resolve().parents[1]
os.environ.setdefault('MPLBACKEND','Agg')
os.environ.setdefault('TF_CPP_MIN_LOG_LEVEL','2')
kernel_dir=Path(sys.prefix)/'share/jupyter/kernels'
ksm=KernelSpecManager(kernel_dirs=[str(kernel_dir)])
requested=sys.argv[1:]
for path in sorted((ROOT/'notebooks').glob('*.ipynb')):
    if requested and not any(path.name.startswith(p) for p in requested): continue
    print('Menjalankan',path.name,flush=True)
    nb=nbformat.read(path,as_version=4)
    client=NotebookClient(nb,timeout=1800,kernel_name='foodsave',kernel_spec_manager=ksm,skip_cells_with_tag='foodsave-legacy',resources={'metadata':{'path':str(path.parent)}})
    try:
        client.execute()
    finally:
        nbformat.write(nb,path)
    print('Selesai',path.name,flush=True)
