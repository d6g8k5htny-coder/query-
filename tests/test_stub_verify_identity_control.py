"""Proposed control (W8, Grok Bot agent 2): stub_verify.main must bind fetched bytes to the stub's
declared identity (byte count AND sha256) and refuse a mismatch with its own handled refusal.

Positive cases: exact bytes are accepted (exit 0, every key reported as verified), so a
reject-everything implementation fails. Negative cases: assert the specific handled refusal --
return code 2, stderr exactly 'REFUSED: identity mismatch for <key>', and no success report on
stdout -- never just "some nonzero exit". Offline: fetch and candidate loading are injected.
Length and digest are each isolated.
"""
from __future__ import annotations
import contextlib,hashlib,io,os,sys,unittest
from pathlib import Path
from unittest import mock
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'));sys.path.insert(0,str(ROOT))
from universal_law_query import stub_verify as v
import verify_portable_stubs as wrapper

def row(key,payload):
    return {'key':key,'repository':'Math-','visibility':'public','commit':'1'*40,'path':'frontiers/'+key+'.py','bytes':len(payload),'sha256':hashlib.sha256(payload).hexdigest()}

class StubIdentityControl(unittest.TestCase):
    def setUp(self):
        patcher=mock.patch.dict(os.environ,{'QUERY_STUB_VERIFY':'1'});patcher.start();self.addCleanup(patcher.stop)

    def run_main(self,rows,served):
        out,err=io.StringIO(),io.StringIO()
        with contextlib.redirect_stdout(out),contextlib.redirect_stderr(err):
            code=v.main([],load_candidates_fn=lambda:rows,fetch_fn=lambda r:served[r['key']])
        return code,out.getvalue(),err.getvalue()

    # --- positive: exact public bytes are accepted ---------------------------------------
    def test_exact_bytes_are_accepted_and_every_key_reported(self):
        rows=[row('a',b'alpha\n'),row('b',b'beta\n')]
        code,out,err=self.run_main(rows,{'a':b'alpha\n','b':b'beta\n'})
        self.assertEqual((code,err),(0,''))
        self.assertIn('"verified": [\n    "a",\n    "b"\n  ]',out)

    # --- negative: the specific handled refusal, not an arbitrary nonzero exit -------------
    def assert_identity_refusal(self,code,out,err,key):
        self.assertEqual(code,2)
        self.assertEqual(err,'REFUSED: identity mismatch for '+key+'\n')
        self.assertEqual(out,'','a refused run must not print a verified report')

    def test_same_length_different_bytes_are_refused(self):
        # Same byte count, different content: only the sha256 comparison can catch this.
        rows=[row('a',b'alpha\n'),row('b',b'beta\n')]
        self.assert_identity_refusal(*self.run_main(rows,{'a':b'alpha\n','b':b'BETA\n'}),'b')

    def test_wrong_length_is_refused(self):
        rows=[row('a',b'alpha\n')]
        self.assert_identity_refusal(*self.run_main(rows,{'a':b'alpha\n\n'}),'a')

    def test_correct_digest_wrong_declared_length_is_refused(self):
        # Correct digest, declared length off by one: only the length comparison can catch this.
        item=row('a',b'alpha\n');item['bytes']=len(b'alpha\n')+1
        self.assert_identity_refusal(*self.run_main([item],{'a':b'alpha\n'}),'a')

    # --- the root compatibility wrapper delegates the same contract ----------------------
    def test_root_wrapper_accepts_exact_and_refuses_substituted_bytes(self):
        good=row('w',b'wrapped\n')
        for served,expected in ((b'wrapped\n',0),(b'WRAPPED\n',2)):
            with self.subTest(served=served):
                out,err=io.StringIO(),io.StringIO()
                with mock.patch.object(wrapper,'load_candidates',return_value=[good]),mock.patch.object(wrapper,'fetch',return_value=served),contextlib.redirect_stdout(out),contextlib.redirect_stderr(err):
                    code=wrapper.main([])
                self.assertEqual(code,expected)
                if expected==0: self.assertEqual(err.getvalue(),'');self.assertIn('"w"',out.getvalue())
                else: self.assertEqual(err.getvalue(),'REFUSED: identity mismatch for w\n');self.assertEqual(out.getvalue(),'')

if __name__=='__main__':unittest.main()
