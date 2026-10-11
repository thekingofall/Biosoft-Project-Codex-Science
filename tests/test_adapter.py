"""Offline regression checks using synthetic source fixtures."""
import hashlib,json,os,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from contextlib import redirect_stdout,redirect_stderr
from io import StringIO
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'code'))
import science_mcp
import codex_science

class AdapterTests(unittest.TestCase):
 def setUp(self):
  parent=os.environ.get('CODEX_SCIENCE_TEST_TMP')
  if parent:Path(parent).mkdir(parents=True,exist_ok=True)
  self.temp=tempfile.TemporaryDirectory(dir=parent);self.root=Path(self.temp.name)
  self.project=self.root/'project';self.project.mkdir();self.release=self.root/'release'
  self.base=self.release/'extracted/asset-text';self.bio=self.base/'mcp-servers/bio-tools'
  self.records=[]
  for relative,data in {'run_server.py':b'# synthetic launcher\n','lib/mcp_bio/domains.json':b'{"sample":["allowed","excluded"]}','lib/mcp_bio/deferred.json':b'{"tools":["excluded"]}'}.items():
   f=self.bio/relative;f.parent.mkdir(parents=True,exist_ok=True);f.write_bytes(data)
   self.records.append({'name':f.relative_to(self.base).as_posix(),'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()})
  self.manifest=self.release/'asset-text-manifest.json';self.save_manifest()
  self.scope=patch.multiple(science_mcp,PROJECT=self.project,RELEASE=self.release,BIO=self.bio);self.scope.start()
  self.env=patch.dict(os.environ,{},clear=True);self.env.start()
 def tearDown(self):self.env.stop();self.scope.stop();self.temp.cleanup()
 def save_manifest(self):self.manifest.write_text(json.dumps(self.records),encoding='utf-8')
 def test_preserves_exclusions_and_counts(self):
  x=science_mcp.prepare();self.assertEqual(x['tool_count'],1);self.assertEqual(x['excluded_count'],1)
 def test_modified_source_rejected(self):
  (self.bio/'run_server.py').write_bytes(b'changed')
  with self.assertRaisesRegex(RuntimeError,'Extracted file changed'):science_mcp.prepare()
 def test_manifest_path_escape_rejected(self):
  self.records.append({'name':'mcp-servers/bio-tools/../../../outside.py','bytes':0,'sha256':''});self.save_manifest()
  with self.assertRaisesRegex(ValueError,'Unexpected path'):science_mcp.prepare()
 def test_missing_assets_actionable(self):
  self.manifest.unlink()
  with self.assertRaisesRegex(RuntimeError,'CODEX_SCIENCE_RELEASE'):science_mcp.prepare()
 def test_credentials_keep_environment_and_hide_values(self):
  os.environ['NCBI_EMAIL']='existing@example.org'
  (self.project/'user-settings.toml').write_text('[credentials]\nNCBI_EMAIL="local@example.org"\nOPENALEX_API_KEY="synthetic-test-key"',encoding='utf-8')
  x=science_mcp.prepare();self.assertEqual(os.environ['NCBI_EMAIL'],'existing@example.org');self.assertTrue(x['credentials_configured']['OPENALEX_API_KEY']);self.assertNotIn('synthetic-test-key',json.dumps(x))
 def test_unknown_setting_rejected(self):
  (self.project/'user-settings.toml').write_text('[credentials]\nUNEXPECTED="value"',encoding='utf-8')
  with self.assertRaisesRegex(ValueError,'Unsupported'):science_mcp.prepare()
 def test_fresh_checkout_status_without_reports(self):
  os.environ['CODEX_HOME']=str(self.project/'codex')
  with patch.multiple(codex_science,PROJECT=self.project,BIO=self.bio),patch.object(sys,'argv',['codex-science','status']),redirect_stdout(StringIO()) as out:
   codex_science.main();x=json.loads(out.getvalue());self.assertIsNone(x['last_online_test_at']);self.assertEqual(x['online_tested_tools'],[])
 def test_missing_catalog_actionable(self):
  with patch.object(codex_science,'PROJECT',self.project),patch.object(sys,'argv',['codex-science','tools']),redirect_stderr(StringIO()) as err:
   with self.assertRaises(SystemExit) as failure:codex_science.main()
   self.assertEqual(failure.exception.code,2);self.assertIn('verify_mcp.py',err.getvalue())
if __name__=='__main__':unittest.main()
