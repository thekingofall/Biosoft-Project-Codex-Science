import importlib,os,sys,tempfile,time,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"code"))

@unittest.skipUnless(sys.platform=="linux","Remote runtime requires Linux")
class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.rt=importlib.import_module("remote_runtime")
        self.tmp=tempfile.TemporaryDirectory(dir=os.environ.get("CODEX_SCIENCE_TEST_TMP"))
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        for area in ("projects","sessions","jobs","reports","runtime"):(self.root/area).mkdir()
        self.change=patch.object(self.rt,"ROOT",self.root);self.change.start();self.addCleanup(self.change.stop)

    def finish(self,jid):
        for _ in range(100):
            result=self.rt.job_status(jid)
            if result["status"] not in ("queued","running"):return result
            time.sleep(.1)
        self.rt.job_cancel(jid)
        self.fail("Worker did not finish in 10 seconds")

    def test_path_and_symlink_escape(self):
        (self.root/"projects/escape").symlink_to(self.root.parent,target_is_directory=True)
        for path in ("../outside","/etc/passwd","projects/escape/file","runtime/daemon.json"):
            with self.assertRaises(ValueError):self.rt.scoped(path)

    def test_file_write_preserves_existing(self):
        self.rt.file_write("projects/data.csv","original")
        with self.assertRaises(FileExistsError):self.rt.file_write("projects/data.csv","replacement")
        for value in ('false',1,None):
            with self.assertRaises(ValueError):self.rt.file_write('projects/data.csv','replacement',overwrite=value)
        self.assertEqual((self.root/"projects/data.csv").read_text(),"original")

    def test_job_success_and_failure(self):
        job=self.rt.job_submit("from pathlib import Path; Path('result.txt').write_text('12'); print('ready')")
        self.assertEqual(self.finish(job['id'])['status'],'succeeded')
        self.assertEqual((self.root/"projects/main/result.txt").read_text(),'12')
        self.assertIn('ready',self.rt.job_logs(job['id'])['text'])
        job=self.rt.job_submit("raise ValueError('expected')")
        result=self.finish(job['id']);self.assertEqual(result['status'],'failed');self.assertNotEqual(result['exit_code'],0)

    def test_cancel_and_timeout(self):
        job=self.rt.job_submit("import time; time.sleep(60)")
        self.rt.job_cancel(job['id']);self.assertEqual(self.finish(job['id'])['status'],'cancelled')
        job=self.rt.job_submit("import time; time.sleep(60)",timeout=1)
        self.assertEqual(self.finish(job['id'])['status'],'timed_out')

    def test_stale_process_identity_is_not_alive(self):
        self.assertFalse(self.rt.alive({'pid':os.getpid(),'start_tick':'wrong'}))
        self.assertTrue(self.rt.alive({'pid':os.getpid(),'start_tick':self.rt.identity(os.getpid())}))

if __name__=='__main__':unittest.main()
