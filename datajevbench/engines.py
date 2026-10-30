"""Optional SystemOne HTTP transport; model-specific inference remains server-owned."""

from __future__ import annotations

import hashlib
import json
import math
import os
import time
import urllib.error
import urllib.parse
import urllib.request

from .core import CriticalInferenceError, validate_response


IDENTITY_FIELDS = {"checkpoint_revision", "backend", "backend_revision", "service_profile_sha256",
                   "inference_config_id", "server_revision", "weight_identity_sha256", "runtime",
                   "model_revision", "revision", "system_fingerprint"}
TRACE_IDENTITY_FIELDS = {"adapter", "upstream_reader_sha256", "adapter_sha256", "prompt_variant",
                         "attention_mode", "backend_kind", "backend_model", "backend_replicas",
                         "thinking", "probability_temperature", "typed_extension",
                         "diagnostic_attention_override"}
CRITICAL_HTTP_CODES = {401, 402, 403, 404, 409, 422, 451}
RETRY_HTTP_CODES = {408, 429, 500, 502, 503, 504}


class TransportFailure(RuntimeError):
    def __init__(self, message: str, attempts: list[dict]):
        super().__init__(message)
        self.attempts = attempts


def _clean(value, secret):
    if isinstance(value, dict):
        return {key: _clean(item, secret) for key, item in value.items()}
    if isinstance(value, list):
        return [_clean(item, secret) for item in value]
    if isinstance(value, str) and secret:
        return value.replace(secret, "[REDACTED]")
    return value


def normalize_answers(body: object, request: dict) -> dict:
    """Convert a SystemOne decision to the frozen benchmark output contract."""
    answers = body.get("answers") if isinstance(body, dict) else None
    if not isinstance(answers, dict) or set(answers) != {"decision"}:
        raise ValueError("SystemOne response must contain exactly the decision answer")
    answer = answers["decision"]
    if not isinstance(answer, dict):
        raise ValueError("Decision answer must be an object")
    kind = answer.get("type")
    if kind is not None and kind != request["question"]["type"]:
        raise ValueError("Decision answer type differs from the question")
    probabilities = answer.get("probabilities")
    if probabilities is not None:
        if not isinstance(probabilities, dict) or set(probabilities) != set(request["labels"]):
            raise ValueError("Decision probabilities must cover the benchmark labels")
        if any(type(p) not in (int, float) or not math.isfinite(p) for p in probabilities.values()):
            raise ValueError("Decision probabilities must be finite numbers")
        # Typed Score is an expectation, and typed Choice can use insertion-order ties.
        # Both are read from the unchanged distribution using the benchmark tie rule.
        choice = answer.get("answer")
        if choice is None:
            choice = min(probabilities, key=lambda label: (-probabilities[label], label))
        result = {"answer": choice, "probabilities": probabilities}
    else:
        if kind == "score" or "score" in answer:
            raise ValueError("Score answers require probabilities; an expectation is not a label")
        result = {"answer": next((answer[key] for key in ("answer", "value", "choice")
                                  if key in answer), None)}
    validate_response(request, result)
    return result


class SystemOneHTTP:
    """Map one DataJevBench question to one SystemOne call without changing its content."""

    def __init__(self, *, endpoint: str, model_id: str, expected_returned_models: list[str] | None = None,
                 timeout_seconds: float = 900, transport_retries: int = 1, retry_delay_seconds: float = 1,
                 key_env: str | None = None):
        parsed = urllib.parse.urlsplit(endpoint)
        try:
            port = parsed.port
        except ValueError as exc:
            raise ValueError("Invalid endpoint port") from exc
        if (parsed.scheme not in {"http", "https"} or not parsed.hostname
                or parsed.path.rstrip("/") != "/v1/systemone" or parsed.query or parsed.fragment
                or parsed.username or parsed.password or (port is not None and not 1 <= port <= 65535)):
            raise ValueError("Endpoint must be an HTTP(S) /v1/systemone URL without embedded credentials")
        if not isinstance(model_id, str) or not model_id:
            raise ValueError("model_id must be nonempty")
        if expected_returned_models is not None and (not isinstance(expected_returned_models, list)
                or not expected_returned_models or
                not all(isinstance(name, str) and name for name in expected_returned_models)):
            raise ValueError("expected_returned_models must contain model IDs")
        if type(transport_retries) is not int or transport_retries < 0:
            raise ValueError("transport_retries must be a nonnegative integer")
        if type(timeout_seconds) not in (int, float) or not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if type(retry_delay_seconds) not in (int, float) or not math.isfinite(retry_delay_seconds) or retry_delay_seconds < 0:
            raise ValueError("retry_delay_seconds must be nonnegative")
        self.endpoint = endpoint
        self.model_id = model_id
        self.expected_returned_models = expected_returned_models
        self.timeout_seconds = timeout_seconds
        self.transport_retries = transport_retries
        self.retry_delay_seconds = retry_delay_seconds
        self.secret = os.environ.get(key_env, "") if key_env else ""
        if key_env and not self.secret:
            raise ValueError(f"Missing credential environment variable: {key_env}")
        self.identity = None

    def bind_identity(self, identity: dict) -> None:
        if self.identity is not None and self.identity != identity:
            raise CriticalInferenceError("Service identity changed on resume")
        self.identity = identity

    @staticmethod
    def wire_payload(request: dict, model_id: str) -> dict:
        if set(request) != {"id", "state", "question", "labels"}:
            raise ValueError("Expected the frozen DataJevBench input projection")
        return {"model": model_id, "state": request["state"],
                "questions": {"decision": request["question"]}}

    def __call__(self, request: dict) -> dict:
        payload = self.wire_payload(request, self.model_id)
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode()
        request_sha = hashlib.sha256(body).hexdigest()
        attempts = []
        for attempt in range(self.transport_retries + 1):
            started = time.monotonic()
            headers = {"Content-Type": "application/json"}
            if self.secret:
                headers["Authorization"] = "Bearer " + self.secret
            wire_request = urllib.request.Request(self.endpoint, data=body, headers=headers)
            try:
                with urllib.request.urlopen(wire_request, timeout=self.timeout_seconds) as response:
                    raw = response.read()
                    status = response.status
                decoded = json.loads(raw)
                attempts.append({"attempt": attempt, "http_status": status,
                                 "seconds": round(time.monotonic() - started, 6)})
                try:
                    result = self._parse(decoded, request)
                except CriticalInferenceError as exc:
                    exc.attempts = attempts
                    raise
                result["_http_receipt"] = {"request_sha256": request_sha,
                                           "response_sha256": hashlib.sha256(raw).hexdigest(),
                                           "attempts": attempts}
                result["_http_response"] = _clean(decoded, self.secret)
                return result
            except urllib.error.HTTPError as exc:
                code = exc.code
                message = exc.read().decode(errors="replace")[:500]
                attempts.append({"attempt": attempt, "http_status": code,
                                 "seconds": round(time.monotonic() - started, 6)})
                if code in CRITICAL_HTTP_CODES:
                    raise CriticalInferenceError(f"HTTP {code}: {_clean(message, self.secret)}", attempts) from None
                if code not in RETRY_HTTP_CODES or attempt == self.transport_retries:
                    raise TransportFailure(f"HTTP {code}: {_clean(message, self.secret)}", attempts) from None
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                attempts.append({"attempt": attempt, "error": type(exc).__name__,
                                 "seconds": round(time.monotonic() - started, 6)})
                if attempt == self.transport_retries:
                    raise TransportFailure(f"Transport failure: {type(exc).__name__}", attempts) from None
            time.sleep(self.retry_delay_seconds * 2 ** attempt)
        raise AssertionError("Unreachable retry loop")

    def _parse(self, body: object, request: dict) -> dict:
        result = self.normalize_response(body, request)
        if self.expected_returned_models and result["_service_identity"]["model"] not in self.expected_returned_models:
            raise CriticalInferenceError("Returned model differs from expected_returned_models")
        self.bind_identity(result["_service_identity"])
        return result

    @staticmethod
    def normalize_response(body: object, request: dict) -> dict:
        """Reconstruct a scored answer and identity from a saved HTTP response."""
        if not isinstance(body, dict) or not isinstance(body.get("model"), str):
            raise CriticalInferenceError("SystemOne response lacks a returned model ID")
        result = normalize_answers(body, request)
        metadata = body.get("metadata", {})
        if not isinstance(metadata, dict):
            raise CriticalInferenceError("SystemOne metadata must be an object")
        identity = {"model": body["model"], "provider": body.get("provider"),
                    "metadata": {key: metadata[key] for key in sorted(IDENTITY_FIELDS) if key in metadata},
                    "system_fingerprint": body.get("system_fingerprint")}
        trace = body.get("evaluation_trace")
        if isinstance(trace, dict) and isinstance(trace.get("inference"), dict):
            stable = trace["inference"]
            identity["inference_trace"] = {key: stable[key] for key in sorted(TRACE_IDENTITY_FIELDS)
                                            if key in stable}
        result["_service_identity"] = identity
        return result


def create_http(**options) -> SystemOneHTTP:
    """Factory for `--engine datajevbench.engines:create_http`."""
    return SystemOneHTTP(**options)
