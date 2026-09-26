from __future__ import annotations
import argparse,json,sys
from pathlib import Path
from .catalog import CatalogError,load_catalog,lookup,verify

def main(argv=None):
    p=argparse.ArgumentParser(description='Read-only source lookup and local byte verification; no network or execution.')
    p.add_argument('--registry',required=True,type=Path)
    group=p.add_mutually_exclusive_group();group.add_argument('--key');group.add_argument('--verify',action='store_true')
    p.add_argument('--workspace',type=Path);args=p.parse_args(argv)
    try:
        data=load_catalog(args.registry)
        if args.verify:
            if args.workspace is None: raise CatalogError('--verify requires --workspace')
            output=verify(data,args.workspace)
        elif args.key: output=lookup(data,args.key)
        else: output={'repositories':data['repositories'],'keys':[row['key'] for row in data['artifacts']],'scientific_status_authority':False}
        print(json.dumps(output,indent=2,sort_keys=True))
    except (OSError,ValueError,KeyError,TypeError) as error:
        print('REFUSED: '+str(error),file=sys.stderr);return 2
    return 0

if __name__=='__main__': raise SystemExit(main())
