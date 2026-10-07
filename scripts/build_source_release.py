from __future__ import annotations
import gzip,hashlib,io,json,subprocess,tarfile,tomllib
from pathlib import Path

STATIC_NAMES=('pyproject.toml','README.md','AGENTS.md','research_query.py','catalog_entry_helper.py','verify_portable_stubs.py','LICENSE','CITATION.cff','SUPPORT.md','SECURITY.md','MANIFEST.in')
# This custom archive is a package payload, not a repository snapshot or a
# setuptools sdist. New source/test members need an explicit contract review.
PACKAGE_NAMES=tuple('src/universal_law_query/'+name for name in (
    '__init__.py','catalog.py','catalog_entry.py','cli.py','stub_verify.py',
))
OFFLINE_TEST_NAMES=tuple('tests/'+name for name in (
    'test_catalog.py','test_catalog_entry.py','test_cli.py',
    'test_stub_verify.py','test_wrapper_parity.py',
))
# LICENSE is the one optional member. Its absence is reported through
# release_eligible; it is never a strict-membership failure.
OPTIONAL_NAMES=('LICENSE',)

def _git(root:Path,*args:str)->str:
    p=subprocess.run(['git','-C',str(root),*args],capture_output=True,text=True,timeout=10,check=False)
    if p.returncode: raise ValueError('git command failed: '+(p.stderr or p.stdout).strip())
    return p.stdout.strip()

def _include_files(root:Path)->list[Path]:
    raw=_git(root,'ls-files','-z','--',*STATIC_NAMES,*PACKAGE_NAMES,*OFFLINE_TEST_NAMES)
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

def _check_strict_members(root:Path,paths:list[Path])->None:
    # A Git pathspec selects; it does not assert exact file membership. A deleted
    # member is silently unmatched, and a directory standing at a listed name
    # returns its descendants. Compare the accepted names with the curated lists.
    allowed={*STATIC_NAMES,*PACKAGE_NAMES,*OFFLINE_TEST_NAMES}
    selected={p.relative_to(root).as_posix() for p in paths}
    missing=sorted(allowed-set(OPTIONAL_NAMES)-selected);unexpected=sorted(selected-allowed)
    if missing or unexpected: raise ValueError('archive membership refused: missing='+repr(missing)+'; unexpected='+repr(unexpected))

def _tarinfo(name:str,data:bytes,epoch:int)->tarfile.TarInfo:
    ti=tarfile.TarInfo(name);ti.size=len(data);ti.mtime=int(epoch);ti.mode=0o644;ti.uid=ti.gid=0;ti.uname=ti.gname='';return ti

def build_source_archive(repo_root:Path,output:Path,source_date_epoch:int,*,strict_members:bool=False)->dict:
    root=Path(repo_root).resolve(strict=True);output=Path(output).resolve()
    if output.is_relative_to(root): raise ValueError('output must be outside repository')
    if not isinstance(source_date_epoch,int) or source_date_epoch<0: raise ValueError('invalid SOURCE_DATE_EPOCH')
    if _git(root,'status','--porcelain'): raise ValueError('working tree must be clean')
    commit=_git(root,'rev-parse','HEAD')
    if len(commit)!=40: raise ValueError('exact commit required')
    # Strict mode selects once and validates membership before project metadata
    # is read, so a missing pyproject.toml is reported as a member and nothing
    # is written. The default call keeps its original order and permissiveness.
    selected=_include_files(root) if strict_members else None
    if selected is not None: _check_strict_members(root,selected)
    meta=tomllib.loads((root/'pyproject.toml').read_text(encoding='utf-8'));project=meta.get('project') or {}
    distribution=project.get('name');version=project.get('version')
    if not isinstance(distribution,str) or not isinstance(version,str): raise ValueError('project name/version required')
    files=[];payloads=[]
    for p in (_include_files(root) if selected is None else selected):
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
