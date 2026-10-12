import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))
import compute_tools as compute


class Handler(BaseHTTPRequestHandler):
    calls = []

    def do_POST(self):
        data = self.rfile.read(int(self.headers["Content-Length"]))
        self.calls.append((self.path, self.headers.get("Authorization"), json.loads(data)))
        if self.path == "/redirect":
            self.send_response(302)
            self.send_header("Location", "/outside")
            self.end_headers()
            return
        body = json.dumps({"prediction": [0.25, 0.75], "echoed_key": "test-secret-123"}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_):
        pass


class ComputeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.addCleanup(self.temp.cleanup)

    def test_job_hashes_and_quotes_arguments(self):
        p = self.root / "input.csv"
        p.write_bytes(b"x,y\n1,2\n")
        result = compute.science_prepare_compute_job(["python", "analysis.py", "sample; touch dangerous"], [str(p)], ["out/result.csv"], scheduler="slurm", partition="gpu", gpus=1)
        self.assertIn("'sample; touch dangerous'", result["script"])
        self.assertIn("#SBATCH --gres=gpu:1", result["script"])
        self.assertEqual(result["state"], "prepared")
        self.assertEqual(result["manifest"]["inputs"][0]["sha256"], hashlib.sha256(p.read_bytes()).hexdigest())
        self.assertEqual(result["manifest"]["script_sha256"], hashlib.sha256(result["script"].encode()).hexdigest())

    def test_rejects_scheduler_injection_and_invalid_resources(self):
        for kwargs in [{"partition": "gpu\n#evil"}, {"job_name": ""}, {"cpus": True}, {"time_minutes": 0}, {"gpus": -1}]:
            with self.assertRaises(ValueError):
                compute.science_prepare_compute_job(["python"], [], [], **kwargs)
        with self.assertRaises(ValueError):
            compute.science_prepare_compute_job(["python"], [], ["../elsewhere"])

    def test_provenance_distinguishes_reported_and_observed(self):
        p = self.root / "result.txt"
        p.write_text("result")
        result = compute.science_capture_compute_result([str(p)], 0, "job-1")
        self.assertEqual(result["process_status_source"], "caller_report")
        self.assertEqual(result["scientific_validation"], "not_assessed")
        self.assertEqual(result["files"][0]["bytes"], 6)
        with self.assertRaises(FileNotFoundError):
            compute.science_capture_compute_result([str(self.root / "missing")])

    def test_local_endpoint_preview_call_redaction_and_redirect(self):
        Handler.calls = []
        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        config = self.root / "endpoints.json"
        config.write_text(json.dumps({"endpoints": {"model": {"base_url": f"http://127.0.0.1:{server.server_port}", "routes": ["/infer", "/redirect"], "api_key_env": "SCIENCE_TEST_KEY", "allow_requests": True}}}))
        with patch.dict(os.environ, {"CODEX_SCIENCE_ENDPOINTS": str(config), "SCIENCE_TEST_KEY": "test-secret-123"}):
            result = compute.science_model_endpoint_request("model", "/infer", {"sequence": "AAA"})
            self.assertEqual(result["state"], "preview")
            self.assertEqual(Handler.calls, [])
            result = compute.science_model_endpoint_request("model", "/infer", {"sequence": "AAA"}, execute=True)
            self.assertEqual(result["state"], "responded")
            self.assertEqual(result["response"]["prediction"], [0.25, 0.75])
            self.assertEqual(result["response"]["echoed_key"], "[redacted]")
            self.assertEqual(Handler.calls[0][1], "Bearer test-secret-123")
            result = compute.science_model_endpoint_request("model", "/redirect", {}, execute=True)
            self.assertEqual(result["http_status"], 302)
            self.assertEqual(len(Handler.calls), 2)
            with self.assertRaises(ValueError):
                compute.science_model_endpoint_request("model", "/outside", {}, execute=True)

    def test_json_escaped_endpoint_credentials_are_redacted_recursively(self):
        # Real JSON escaping must be decoded before matching the credential.
        for key in ('test"credential', 'test\\credential', 'test-\u03b1-credential'):
            with self.subTest(credential_format="JSON-escaped"):
                response_body = json.dumps({
                    "echoed_key": key,
                    "nested": ["Bearer " + key, {key: "prefix " + key + " suffix"}],
                    "prediction": [0.25, 0.75],
                }).encode("utf-8")
                class Response:
                    status = 200
                    def __enter__(self): return self
                    def __exit__(self, *_): pass
                    def read(self, *_): return response_body
                class Opener:
                    def open(self, *_, **__): return Response()
                endpoint = {"api_key_env": "SCIENCE_TEST_KEY", "allow_requests": True}
                with patch.object(compute, "_endpoint", return_value=(endpoint, "http://127.0.0.1/infer")), patch.dict(os.environ, {"SCIENCE_TEST_KEY": key}), patch.object(compute.urllib.request, "build_opener", return_value=Opener()):
                    result = compute.science_model_endpoint_request("model", "/infer", {}, execute=True)
                self.assertEqual(result["state"], "responded")
                self.assertEqual(result["response"]["echoed_key"], "[redacted]")
                self.assertEqual(result["response"]["nested"], ["Bearer [redacted]", {"[redacted]": "prefix [redacted] suffix"}])
                self.assertEqual(result["response"]["prediction"], [0.25, 0.75])
                self.assertNotIn(key, json.dumps(result, ensure_ascii=False))

    def test_remote_transport_and_permission_validation(self):
        config = self.root / "endpoints.json"
        for endpoint in [{"base_url": "http://example.org", "routes": ["/infer"]}, {"base_url": "https://example.org", "routes": ["/infer"], "allow_requests": False}]:
            config.write_text(json.dumps({"endpoints": {"model": endpoint}}))
            with patch.dict(os.environ, {"CODEX_SCIENCE_ENDPOINTS": str(config)}):
                with self.assertRaises(ValueError):
                    compute.science_model_endpoint_request("model", "/infer", {}, execute=True)

    def test_model_recipes_have_sources_and_distinguish_runtime(self):
        catalogue = compute.science_model_recipe()
        self.assertEqual(len(catalogue["models"]), 14)
        for item in catalogue["models"]:
            recipe = compute.science_model_recipe(item["name"])
            self.assertEqual(len(recipe["source"]["sha256"]), 64)
            self.assertFalse(recipe["runtime_tested"])
            self.assertTrue(recipe["inputs"])
            self.assertTrue(recipe["invocation"])
        recipe = compute.science_model_recipe("boltz")
        self.assertEqual(recipe["input_example"]["version"], 1)
        recipe["inputs"].clear()
        self.assertTrue(compute.science_model_recipe("boltz")["inputs"])
        with self.assertRaises(ValueError):
            compute.science_model_recipe("unknown-model")

    def test_mcp_registration(self):
        class Fake:
            def __init__(self): self.names = []
            def tool(self):
                return lambda fn: self.names.append(fn.__name__)
        fake = Fake()
        compute.register_tools(fake)
        self.assertEqual(len(fake.names), 5)
        self.assertTrue(all(n.startswith("science_") for n in fake.names))


if __name__ == "__main__":
    unittest.main()
