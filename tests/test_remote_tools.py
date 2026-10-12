import hashlib
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))
import remote_tools as rt

class RemoteTransferTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(dir=os.environ.get("CODEX_SCIENCE_TEST_TMP"))
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.info={"absolute_path":"/remote/result.csv","bytes":3,"sha256":hashlib.sha256(b"abc").hexdigest()}
        self.client=MagicMock()
        self.sftp=self.client.open_sftp.return_value.__enter__.return_value

    def fetch(self, output="result.csv"):
        with patch.object(rt,"request",return_value=self.info),patch.object(rt,"connect",return_value=(self.client,{})):
            return rt.science_fetch_artifact("projects/main/result.csv",str(self.root),output)

    def test_verified_download(self):
        self.sftp.getfo.side_effect=lambda path,out:out.write(b"abc")
        self.assertEqual(self.fetch()["sha256"],self.info["sha256"])
        self.assertEqual((self.root/"result.csv").read_bytes(),b"abc")

    def test_network_failure_removes_partial_file(self):
        def fail(path,out):
            out.write(b"a")
            raise OSError("connection lost")
        self.sftp.getfo.side_effect=fail
        with self.assertRaises(OSError):self.fetch()
        self.assertFalse((self.root/"result.csv").exists())

    def test_hash_mismatch_removes_bad_file(self):
        self.sftp.getfo.side_effect=lambda path,out:out.write(b"bad")
        with self.assertRaises(RuntimeError):self.fetch()
        self.assertFalse((self.root/"result.csv").exists())

    def test_existing_output_preserved(self):
        (self.root/"result.csv").write_text("keep")
        with self.assertRaises(FileExistsError):self.fetch()
        self.assertEqual((self.root/"result.csv").read_text(),"keep")
        self.client.open_sftp.assert_not_called()

    def test_outside_paths_rejected_before_network(self):
        with patch.object(rt,"request") as request:
            for path in ["../escape.csv",str(self.root/"absolute.csv"),"."]:
                with self.assertRaises(ValueError):rt.science_fetch_artifact("projects/main/x",str(self.root),path)
            request.assert_not_called()

    def test_large_artifact_not_transferred(self):
        self.info["bytes"]=101*1024*1024
        with self.assertRaises(ValueError):self.fetch()
        self.client.open_sftp.assert_not_called()

    def test_connection_timeout_retry_before_submission(self):
        import paramiko
        cfg={"known_hosts":"unused","host":"example.org","user":"researcher","password_env":"SCIENCE_TEST_PASSWORD","host_key_sha256":hashlib.sha256(b"saved-key").hexdigest()}
        key=MagicMock();key.asbytes.return_value=b"saved-key"
        keys=MagicMock();keys.lookup.return_value={"ssh-rsa":key}
        with patch.object(rt,"config",return_value=cfg),patch.object(paramiko,"HostKeys",return_value=keys),patch.object(paramiko,"SSHClient") as ssh,patch.dict(os.environ,{"SCIENCE_TEST_PASSWORD":"test-only"}),patch.object(rt.time,"sleep"):
            ssh.return_value.connect.side_effect=[TimeoutError("transient"),None]
            client,_=rt.connect()
            self.assertEqual(client.connect.call_count,2)
            client.exec_command.assert_not_called()

    def test_unverified_host_key_rejected(self):
        import paramiko
        cfg={"known_hosts":"unused","host":"example.org","host_key_sha256":"wrong"}
        keys=MagicMock();keys.lookup.return_value={"ssh-rsa":MagicMock()}
        keys.lookup.return_value["ssh-rsa"].asbytes.return_value=b"saved-key"
        with patch.object(rt,"config",return_value=cfg),patch.object(paramiko,"HostKeys",return_value=keys),patch.object(paramiko,"SSHClient") as ssh:
            with self.assertRaisesRegex(RuntimeError,"fingerprint"):rt.connect()
            ssh.return_value.connect.assert_not_called()

if __name__=="__main__":unittest.main()
