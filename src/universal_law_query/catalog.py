from __future__ import annotations
import hashlib,json,re
from pathlib import Path,PurePosixPath

class CatalogError(ValueError):
    pass

def unique(pairs):
    out={}
    for key,value in pairs:
        if key in out: raise CatalogError('duplicate JSON key')
        out[key]=value
    return out

def valid_path(text):
    if not isinstance(text,str) or not text or '\\' in text or ':' in text: raise CatalogError('unsafe path')
    path=PurePosixPath(text)
    if not path.parts or path.is_absolute() or '..' in path.parts or str(path)!=text: raise CatalogError('unsafe path')
    return path

def load_catalog(path):
    file=Path(path)
    if file.stat().st_size>1000000: raise CatalogError('catalog exceeds size bound')
    data=json.loads(file.read_text(encoding='utf-8'),object_pairs_hook=unique)
    if not isinstance(data,dict) or type(data.get('schema_version')) is not int or data['schema_version']!=1 or data.get('scientific_status_authority') is not False: raise CatalogError('unsupported catalog or false status authority')
    repos=data.get('repositories')
    if not isinstance(repos,dict) or not repos: raise CatalogError('repository map required')
    for name,row in repos.items():
        if not re.fullmatch(r'[A-Za-z0-9_.-]+',name) or name in ('.','..'): raise CatalogError('invalid repository name')
        if not isinstance(row,dict) or row.get('full_name')!='d6g8k5htny-coder/'+name: raise CatalogError('unexpected owner')
        if row.get('visibility') not in ('public','private'): raise CatalogError('missing visibility')
    entries=data.get('artifacts')
    if not isinstance(entries,list): raise CatalogError('artifact list required')
    keys=set()
    for row in entries:
        if not isinstance(row,dict): raise CatalogError('artifact must be an object')
        key=row.get('key')
        if not isinstance(key,str) or not key or key in keys: raise CatalogError('missing or duplicate artifact key')
        keys.add(key)
        if row.get('repository') not in repos: raise CatalogError('unknown repository')
        if repos[row['repository']]['visibility']!='public' or row.get('visibility')!='public': raise CatalogError('private artifacts cannot enter this public catalog')
        valid_path(row.get('path'))
        if not isinstance(row.get('commit'),str) or not re.fullmatch('[0-9a-f]{40}',row['commit']): raise CatalogError('exact commit required')
        if not isinstance(row.get('sha256'),str) or not re.fullmatch('[0-9a-f]{64}',row['sha256']): raise CatalogError('exact SHA256 required')
        if type(row.get('bytes')) is not int or not 0<=row['bytes']<=10000000: raise CatalogError('invalid byte count')
        if not isinstance(row.get('scope'),str) or not row['scope']: raise CatalogError('exact scope required')
    return data

def lookup(data,key):
    matches=[x for x in data['artifacts'] if x['key']==key]
    if len(matches)!=1: raise CatalogError('UNKNOWN_KEY: '+key)
    return dict(matches[0],catalog_is_not_acceptance=True)

def verify(data,workspace):
    root=Path(workspace).resolve(strict=True);checked=[]
    for row in data['artifacts']:
        rel=valid_path(row['repository']+'/'+row['path']);path=root
        for part in rel.parts:
            path=path/part
            if path.is_symlink(): raise CatalogError('symlink payload refused: '+row['key'])
        if not path.is_file() or not path.resolve().is_relative_to(root): raise CatalogError('missing/outside payload: '+row['key'])
        if path.stat().st_size!=row['bytes']: raise CatalogError('byte count mismatch: '+row['key'])
        raw=path.read_bytes()
        if hashlib.sha256(raw).hexdigest()!=row['sha256']: raise CatalogError('hash mismatch: '+row['key'])
        checked.append(row['key'])
    return {'verified':checked,'meaning':'exact bytes only; not currentness or theorem acceptance'}
