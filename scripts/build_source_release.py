from __future__ import annotations
import gzip,hashlib,io,json,subprocess,tarfile,tomllib
from pathlib import Path

STATIC_NAMES=('pyproject.toml','README.md','AGENTS.md','research_query.py','catalog_entry_helper.py','verify_portable_stubs.py','LICENSE')
TREE_ROOTS=('src','tests')

def _git(root:Path,*args:str)->str:
    p=subprocess.run(['git','-C',str(root),*args],capture_output=True,text=True,timeout=10,check=False)
    if p.returncode: raise ValueError('git command failed: '+(p.stderr or p.stdout).strip())
    return p.stdout.strip()

def _include_files(root:Path)->list[Path]:
    raw=_git(root,'ls-files','-z','--',*STATIC_NAMES,*TREE_ROOTS)
    out=[]
    for reltext in (x for x in raw.split('\0') if x):
        rel=Path(reltext)
        if any(part.casefold() in {'sandbox','__pycache__','.git'} for part in rel.parts): raise ValueError('private/generated path refused: '+reltext)
        if rel.suffix in {'.pyc','.pyo'}: raise ValueError('compiled payload refused: '+reltext)
        path=root/rel
        if path.is_symlink(): raise ValueError('symlink payload refused: '+reltext)
        if not path.is_file(): raise ValueError('tracked payload is not a regular file: '+reltext)
        out.append(path)
    return sorted(out,key=lambda p:p.relative_to(root).as_posix())

def _tarinfo(name:str,data:bytes,epoch:int)->tarfile.TarInfo:
    ti=tarfile.TarInfo(name);ti.size=len(data);ti.mtime=int(epoch);ti.mode=0o644;ti.uid=ti.gid=0;ti.uname=ti.gname='';return ti

def build_source_archive(repo_root:Path,output:Path,source_date_epoch:int)->dict:
    root=Path(repo_root).resolve(strict=True);output=Path(output).resolve()
    if output.is_relative_to(root): raise ValueError('output must be outside repository')
    if not isinstance(source_date_epoch,int) or source_date_epoch<0: raise ValueError('invalid SOURCE_DATE_EPOCH')
    if _git(root,'status','--porcelain'): raise ValueError('working tree must be clean')
    commit=_git(root,'rev-parse','HEAD')
    if len(commit)!=40: raise ValueError('exact commit required')
    meta=tomllib.loads((root/'pyproject.toml').read_text(encoding='utf-8'));project=meta.get('project') or {}
    distribution=project.get('name');version=project.get('version')
    if not isinstance(distribution,str) or not isinstance(version,str): raise ValueError('project name/version required')
    files=[];payloads=[]
    for p in _include_files(root):
        rel=p.relative_to(root).as_posix()
        raw=p.read_bytes();files.append({'path':rel,'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw)});payloads.append((rel,raw))
    eligible=any(row['path']=='LICENSE' for row in files)
    manifest={'schema_version':'1.0','distribution':distribution,'version':version,'repository':'d6g8k5htny-coder/query-','commit':commit,'scientific_status_authority':False,'release_eligible':eligible,'files':files}
    manifest_raw=(json.dumps(manifest,sort_keys=True,indent=2)+'\n').encode()
    build={'schema_version':'1.0','repository':'d6g8k5htny-coder/query-','commit':commit,'source_date_epoch':source_date_epoch,'builder':'universal-law-query-source-builder-v1'}
    build_raw=(json.dumps(build,sort_keys=True,indent=2)+'\n').encode()
    output.parent.mkdir(parents=True,exist_ok=True)
    with output.open('wb') as fh:
        with gzip.GzipFile(filename='',mode='wb',fileobj=fh,compresslevel=9,mtime=source_date_epoch) as gz:
            with tarfile.open(fileobj=gz,mode='w',format=tarfile.USTAR_FORMAT) as tf:
                for name,raw in [*payloads,('BUILD_INFO.json',build_raw),('SOURCE_MANIFEST.json',manifest_raw)]: tf.addfile(_tarinfo(name,raw,source_date_epoch),io.BytesIO(raw))
    archive_sha=hashlib.sha256(output.read_bytes()).hexdigest()
    return {'archive_sha256':archive_sha,'manifest_sha256':hashlib.sha256(manifest_raw).hexdigest(),'commit':commit,'release_eligible':eligible,'file_count':len(files)}
