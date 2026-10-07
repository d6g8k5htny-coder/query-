from __future__ import annotations
import gzip,hashlib,io,json,os,subprocess,tarfile,tomllib
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
# `git -C root` does not bind a command to root. An inherited GIT_DIR selects
# another repository, whose commit would then be recorded, and an inherited
# GIT_INDEX_FILE hides a staged change. Git's own list of repository-local
# variables is `git rev-parse --local-env-vars`. No Git call below inherits
# any of them, so repo_root alone names the repository. Four are kept on
# purpose: GIT_CONFIG, GIT_CONFIG_PARAMETERS and GIT_CONFIG_COUNT carry
# settings such as safe.directory and select no repository, and
# GIT_NO_REPLACE_OBJECTS can only make Git read the stored objects.
REPOSITORY_ENV_NAMES=('GIT_DIR','GIT_WORK_TREE','GIT_IMPLICIT_WORK_TREE','GIT_COMMON_DIR','GIT_INDEX_FILE','GIT_OBJECT_DIRECTORY','GIT_ALTERNATE_OBJECT_DIRECTORIES','GIT_REPLACE_REF_BASE','GIT_GRAFT_FILE','GIT_SHALLOW_FILE','GIT_PREFIX')

def _git_env()->dict:
    return {name:value for name,value in os.environ.items() if name not in REPOSITORY_ENV_NAMES}

def _git(root:Path,*args:str)->str:
    p=subprocess.run(['git','-C',str(root),*args],capture_output=True,text=True,timeout=10,check=False,env=_git_env())
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

def _git_identity(root:Path,*args:str)->bytes:
    # Identity lookups must read the named commit's own objects. A refs/replace
    # entry would otherwise substitute another commit's tree while rev-parse
    # still reports the original commit.
    p=subprocess.run(['git','--no-replace-objects','-C',str(root),*args],capture_output=True,timeout=10,check=False,env=_git_env())
    if p.returncode: raise ValueError('git command failed: '+p.stderr.decode(errors='replace').strip())
    return p.stdout

def _check_commit_entries(root:Path,commit:str,names:list[str])->None:
    # The checkout's view is not the commit's. The index can hold a different
    # member set than the commit named in the manifest, and with
    # core.symlinks=false a symlink entry is checked out as a regular file
    # holding the link target. Take members and file types from the commit's tree.
    entries={}
    for entry in _git_identity(root,'ls-tree','-z',commit,'--',*STATIC_NAMES,*PACKAGE_NAMES,*OFFLINE_TEST_NAMES).decode().split('\0'):
        if not entry: continue
        meta,_,name=entry.partition('\t');mode,kind,_=meta.split(' ',2);entries[name]=(mode,kind)
    commit_only=sorted(set(entries)-set(names));checkout_only=sorted(set(names)-set(entries))
    if commit_only or checkout_only: raise ValueError('commit and checkout disagree on members: commit only='+repr(commit_only)+'; checkout only='+repr(checkout_only))
    irregular=sorted(name for name,(mode,kind) in entries.items() if kind!='blob' or mode not in ('100644','100755'))
    if irregular: raise ValueError('not a regular file in the commit: '+', '.join(irregular))

def _committed_bytes(root:Path,commit:str,rel:str)->bytes:
    return _git_identity(root,'cat-file','blob',commit+':'+rel)

def _head_commit(root:Path)->str:
    # `rev-parse HEAD` prints whatever HEAD names. That can be an annotated tag
    # object, which status, ls-tree and cat-file all peel without a word, so a
    # tag ID would be recorded as the commit. Ask for the commit itself, and
    # refuse a HEAD that does not lead to one.
    try: return _git_identity(root,'rev-parse','--verify','--quiet','HEAD^{commit}').decode().strip()
    except ValueError: raise ValueError('HEAD does not name a commit') from None

def _tarinfo(name:str,data:bytes,epoch:int)->tarfile.TarInfo:
    ti=tarfile.TarInfo(name);ti.size=len(data);ti.mtime=int(epoch);ti.mode=0o644;ti.uid=ti.gid=0;ti.uname=ti.gname='';return ti

def build_source_archive(repo_root:Path,output:Path,source_date_epoch:int,*,strict_members:bool=False)->dict:
    root=Path(repo_root).resolve(strict=True);output=Path(output).resolve()
    if output.is_relative_to(root): raise ValueError('output must be outside repository')
    if not isinstance(source_date_epoch,int) or source_date_epoch<0: raise ValueError('invalid SOURCE_DATE_EPOCH')
    if _git(root,'status','--porcelain'): raise ValueError('working tree must be clean')
    commit=_head_commit(root)
    if len(commit)!=40: raise ValueError('exact commit required')
    # Strict mode selects once and validates membership before project metadata
    # is read, so a missing pyproject.toml is reported as a member. It then
    # requires the commit's own tree to hold the same members as regular files,
    # and binds every payload to its committed blob below. All of these refusals
    # happen before any output exists. The default call keeps its original order
    # and permissiveness.
    selected=_include_files(root) if strict_members else None
    if selected is not None:
        _check_strict_members(root,selected)
        _check_commit_entries(root,commit,[p.relative_to(root).as_posix() for p in selected])
    meta=tomllib.loads((root/'pyproject.toml').read_text(encoding='utf-8'));project=meta.get('project') or {}
    distribution=project.get('name');version=project.get('version')
    if not isinstance(distribution,str) or not isinstance(version,str): raise ValueError('project name/version required')
    files=[];payloads=[]
    for p in (_include_files(root) if selected is None else selected):
        rel=p.relative_to(root).as_posix()
        raw=p.read_bytes()
        # A clean status does not prove these are the commit's bytes: index hints
        # (assume-unchanged, skip-worktree) and checkout filters can hide a
        # difference. Strict mode refuses it instead of normalizing either side.
        if selected is not None and raw!=_committed_bytes(root,commit,rel): raise ValueError('payload differs from its committed blob: '+rel)
        files.append({'path':rel,'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw)});payloads.append((rel,raw))
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
