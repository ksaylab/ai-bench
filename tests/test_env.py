import json
import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from unittest import mock

from aibench import env

REMOTE_HW = {"os": "Linux 7.2", "arch": "x86_64", "cpu": "Some x86 CPU", "ram_gib": 15.5,
             "gpus": [{"name": "Some NVIDIA card", "vram_mib": 8192, "driver": "615"}], "python": "3.14",
             "llama_cpp": "version: 0.6.0", "ollama": ""}


class Router(BaseHTTPRequestHandler):
    """llama-server in router mode: /props has no model, /v1/models lists each preset with its arguments."""

    def do_GET(self):
        if self.path == "/props":
            body = {"role": "router", "model_path": "none", "build_info": "b1-abc"}
        elif self.path == "/v1/models":
            body = {"data": [{"id": "small", "status": {"args": ["llama-server", "--model", "/srv/m/Small-Q4.gguf",
                                                                 "--port", "0"]}},
                             {"id": "other", "status": {"args": ["llama-server", "--model", "/srv/m/Other.gguf"]}}]}
        else:
            self.send_error(404)
            return
        data = json.dumps(body).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *_):
        pass


class TestEnvRemoteServer(unittest.TestCase):
    def router(self):
        srv = HTTPServer(("127.0.0.1", 0), Router)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        self.addCleanup(srv.server_close)
        self.addCleanup(srv.shutdown)
        return f"http://127.0.0.1:{srv.server_port}/v1"

    def test_remote_server_hardware_comes_from_the_server_not_from_this_machine(self):
        with mock.patch.object(env, "remote", return_value=dict(REMOTE_HW)) as remote:
            e = env.capture("pc-rtx2060", "http://gpu-box.invalid/v1", server_host="gpu-box")
        remote.assert_called_once_with("gpu-box")
        self.assertEqual(e["machine"], "pc-rtx2060")
        self.assertEqual(e["cpu"], "Some x86 CPU")
        self.assertEqual(e["gpus"][0]["name"], "Some NVIDIA card")

    def test_remote_server_without_ssh_host_records_no_hardware(self):
        e = env.capture("pc-rtx2060", "http://gpu-box.invalid/v1")
        for field in ("os", "cpu", "ram_gib", "gpus"):
            self.assertNotIn(field, e)
        self.assertIn("AIBENCH_SERVER_HOST", e["hardware"])

    def test_runpod_through_a_local_tunnel_is_a_remote_server(self):
        e = env.capture("runpod", self.router())
        self.assertNotIn("cpu", e)
        self.assertIn("hardware", e)

    def test_local_server_still_records_this_machine(self):
        e = env.capture("pc-rtx2060", self.router())
        self.assertIn("cpu", e)
        self.assertNotIn("hardware", e)

    def test_failed_ssh_records_no_hardware(self):
        with mock.patch.object(env, "remote", return_value={}):
            e = env.capture("pc-rtx2060", "http://gpu-box.invalid/v1", server_host="gpu-box")
        self.assertNotIn("cpu", e)
        self.assertIn("hardware", e)

    def test_router_mode_records_the_gguf_of_each_model_without_its_path(self):
        e = env.capture("pc-rtx2060", self.router(), models=["small", "missing"])
        self.assertEqual(e["server"], {"build": "b1-abc", "gguf": {"small": "Small-Q4.gguf"}})

    def test_the_source_sent_over_ssh_runs_on_its_own(self):
        # the same stdin ssh would get, run by a local isolated interpreter instead of the remote one
        hw = env.remote("unused", command=[sys.executable, "-I", "-"])
        for field in ("os", "arch", "cpu", "ram_gib", "gpus", "python"):
            self.assertIn(field, hw)
        self.assertNotIn("machine", hw)

    def test_remote_failure_returns_nothing(self):
        self.assertEqual(env.remote("unused", command=[sys.executable, "-c", "import sys; sys.exit(3)"]), {})


if __name__ == "__main__":
    unittest.main()
