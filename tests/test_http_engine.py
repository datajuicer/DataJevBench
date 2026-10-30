"""Check the wire boundary and stop conditions of the optional HTTP engine."""

import io
import json
import tempfile
import threading
import unittest
import urllib.error
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from unittest.mock import patch

from datajevbench.core import CriticalInferenceError, read_jsonl, run_evaluation, score_run
from datajevbench.engines import SystemOneHTTP


class Response:
    status = 200

    def __init__(self, body):
        self.body = json.dumps(body).encode()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def read(self):
        return self.body


def input_row(iid):
    return {"id": iid, "state": {"messages": []},
            "question": {"type": "choice", "instructions": "Choose.",
                         "criteria": {"A": "first", "B": "second"}},
            "labels": ["A", "B"]}


def model_response(model):
    return {"model": model, "answers": {"decision": {"probabilities": {"A": 0.8, "B": 0.2}}},
            "metadata": {"backend_revision": "r1"},
            "evaluation_trace": {"inference": {"backend_kind": "reference", "adapter_sha256": "abc"}}}


class HTTPTest(unittest.TestCase):
    def engine(self):
        return SystemOneHTTP(endpoint="http://127.0.0.1:8000/v1/systemone", model_id="toy",
                             expected_returned_models=["toy-v1", "toy-v2"], transport_retries=0)

    def test_payload_excludes_id_and_gold_and_keeps_candidate_order(self):
        captured = []

        def send(request, timeout):
            captured.append(json.loads(request.data))
            return Response(model_response("toy-v1"))

        with patch("urllib.request.OpenerDirector.open", side_effect=send):
            result = self.engine()(input_row("one"))
        self.assertEqual(set(captured[0]), {"model", "state", "questions"})
        self.assertEqual(list(captured[0]["questions"]["decision"]["criteria"]), ["A", "B"])
        self.assertEqual(result["answer"], "A")
        self.assertEqual(result["_service_identity"]["model"], "toy-v1")
        self.assertEqual(len(result["_http_receipt"]["request_sha256"]), 64)

    def test_local_http_service_round_trip(self):
        received = []

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                length = int(self.headers["Content-Length"])
                self.server.received.append((self.path, json.loads(self.rfile.read(length))))
                body = json.dumps(model_response("toy-v1")).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *_):
                pass

        server = HTTPServer(("127.0.0.1", 0), Handler)
        server.received = received
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        try:
            engine = SystemOneHTTP(endpoint=f"http://127.0.0.1:{server.server_port}/v1/systemone",
                                   model_id="toy", expected_returned_models=["toy-v1"])
            result = engine(input_row("one"))
        finally:
            server.shutdown()
            server.server_close()
            worker.join(timeout=2)
        self.assertEqual(result["answer"], "A")
        self.assertEqual(received[0][0], "/v1/systemone")
        self.assertEqual(set(received[0][1]), {"model", "state", "questions"})

    def test_label_only_systemone_answer_remains_label_only(self):
        body = {"model": "toy-v1", "answers": {"decision": {"choice": "B"}}}
        with patch("urllib.request.OpenerDirector.open", return_value=Response(body)):
            result = self.engine()(input_row("one"))
        self.assertEqual(result["answer"], "B")
        self.assertNotIn("probabilities", result)

    def test_redirects_stop_without_forwarding_credentials_or_retrying(self):
        received = []

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                self.rfile.read(int(self.headers.get("Content-Length", 0)))
                self.do_GET()

            def do_GET(self):
                received.append((self.server.server_port, self.path,
                                 self.headers.get("Authorization")))
                if self.path == "/v1/systemone":
                    self.send_response(self.server.redirect_code)
                    self.send_header("Location", self.server.destination)
                else:
                    self.send_response(200)
                self.send_header("Content-Length", "0")
                self.end_headers()

            def log_message(self, *_):
                pass

        servers = []
        try:
            for _ in range(2):
                server = HTTPServer(("127.0.0.1", 0), Handler)
                worker = threading.Thread(target=server.serve_forever, daemon=True)
                worker.start()
                servers.append((server, worker))
            origin, target = [server for server, _ in servers]
            with patch.dict("os.environ", {"DATAJEV_TEST_KEY": "local-probe-secret",
                                           "no_proxy": "*"}):
                engine = SystemOneHTTP(
                    endpoint=f"http://127.0.0.1:{origin.server_port}/v1/systemone",
                    model_id="toy", key_env="DATAJEV_TEST_KEY", transport_retries=3,
                    retry_delay_seconds=0, timeout_seconds=2)
                for code in (301, 302, 303, 307, 308):
                    for destination in (origin, target):
                        with self.subTest(code=code, port=destination.server_port):
                            received.clear()
                            origin.redirect_code = code
                            origin.destination = f"http://127.0.0.1:{destination.server_port}/capture"
                            with self.assertRaisesRegex(CriticalInferenceError,
                                                        "redirects are disabled") as caught:
                                engine(input_row("one"))
                            self.assertEqual(received, [(origin.server_port, "/v1/systemone",
                                                         "Bearer local-probe-secret")])
                            self.assertEqual(len(caught.exception.attempts), 1)
                            self.assertEqual(caught.exception.attempts[0]["http_status"], code)
        finally:
            for server, worker in servers:
                server.shutdown()
                server.server_close()
                worker.join(timeout=2)

    def test_identity_change_stops_run_and_resume(self):
        assets = {"inputs": [input_row("one"), input_row("two")],
                  "dataset_sha256": "dataset", "inputs_sha256": "inputs", "scorer_sha256": "scorer"}
        identity = {"engine": "datajevbench.engines:create_http"}
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            with patch("urllib.request.OpenerDirector.open", side_effect=[Response(model_response("toy-v1")),
                                                             Response(model_response("toy-v2"))]):
                with self.assertRaises(CriticalInferenceError):
                    run_evaluation(assets, directory / "run", self.engine(), identity)
            log = read_jsonl(directory / "run/results.jsonl")
            self.assertEqual([row["status"] for row in log], ["ok", "error"])
            with patch("urllib.request.OpenerDirector.open", return_value=Response(model_response("toy-v2"))):
                with self.assertRaises(CriticalInferenceError):
                    run_evaluation(assets, directory / "run", self.engine(), identity, resume=True)

    def test_auth_failure_is_critical_without_retry(self):
        error = urllib.error.HTTPError("http://127.0.0.1:8000/v1/systemone", 401,
                                       "Unauthorized", {}, io.BytesIO(b"invalid key"))
        engine = self.engine()
        engine.transport_retries = 3
        with patch("urllib.request.OpenerDirector.open", side_effect=error) as send:
            with self.assertRaises(CriticalInferenceError):
                engine(input_row("one"))
        self.assertEqual(send.call_count, 1)

    def test_offline_score_replays_saved_http_response(self):
        request = input_row("one")
        task = {**request, "expected": "A", "provenance": {"subset": "D1"}}
        assets = {"inputs": [request], "tasks": [task], "manifest": {"by_subset": {"D1": 1}},
                  "dataset_sha256": "dataset", "inputs_sha256": "inputs", "scorer_sha256": "scorer"}
        identity = {"engine": "datajevbench.engines:create_http",
                    "engine_options": {"model_id": "toy", "expected_returned_models": ["toy-v1"]}}
        with tempfile.TemporaryDirectory() as directory:
            run_dir = Path(directory) / "run"
            with patch("urllib.request.OpenerDirector.open", return_value=Response(model_response("toy-v1"))):
                run_evaluation(assets, run_dir, self.engine(), identity)
            self.assertEqual(score_run(assets, run_dir)["overall"]["accuracy"], 1.0)
            log_path = run_dir / "results.jsonl"
            event = read_jsonl(log_path)[0]
            event["raw_output"]["answer"] = "B"
            event["raw_output"]["probabilities"] = {"A": 0.2, "B": 0.8}
            event["prediction"]["answer"] = "B"
            event["prediction"]["probabilities"] = {"A": 0.2, "B": 0.8}
            log_path.write_text(json.dumps(event) + "\n")
            with self.assertRaisesRegex(ValueError, "HTTP normalization differs"):
                score_run(assets, run_dir)

    def test_same_model_with_changed_backend_trace_stops(self):
        first = model_response("toy-v1")
        second = model_response("toy-v1")
        second["evaluation_trace"]["inference"]["backend_kind"] = "replacement"
        engine = self.engine()
        with patch("urllib.request.OpenerDirector.open", side_effect=[Response(first), Response(second)]):
            engine(input_row("one"))
            with self.assertRaises(CriticalInferenceError):
                engine(input_row("two"))


if __name__ == "__main__":
    unittest.main()
