"""Bridge model-owned predict(state, questions) implementations without GPU dependencies."""

from copy import deepcopy
import importlib
from pathlib import Path

from .core import CriticalInferenceError, sha256
from .engines import normalize_answers


class PredictAdapter:
    def __init__(self, *, factory: str, factory_options: dict | None = None,
                 source_files: list[str] | None = None):
        if not isinstance(factory, str) or factory.count(":") != 1:
            raise ValueError("factory must use module:attribute syntax")
        if factory_options is not None and not isinstance(factory_options, dict):
            raise ValueError("factory_options must be an object")
        if source_files is not None and (not isinstance(source_files, list)
                or not all(isinstance(path, str) for path in source_files)):
            raise ValueError("source_files must be a list of paths")
        module_name, attribute = factory.split(":")
        module = importlib.import_module(module_name)
        paths = {Path(path).resolve() for path in (source_files or [])}
        paths.add(Path(module.__file__).resolve())
        self.source_hashes = {str(path): sha256(path) for path in sorted(paths)}
        self.backend = getattr(module, attribute)(**deepcopy(factory_options or {}))
        if not callable(getattr(self.backend, "predict", None)):
            raise TypeError("Factory must return an object with predict(state, questions)")

    def __call__(self, request: dict) -> dict:
        if set(request) != {"id", "state", "question", "labels"}:
            raise ValueError("Expected the frozen DataJevBench input projection")
        try:
            body = self.backend.predict(deepcopy(request["state"]),
                                        {"decision": deepcopy(request["question"])})
        except Exception as exc:
            if getattr(exc, "critical", False):
                raise CriticalInferenceError(str(exc), getattr(exc, "attempts", None)) from exc
            raise
        result = normalize_answers(body, request)
        result["_predict_response"] = body
        return result


def create_predict(**options) -> PredictAdapter:
    """Factory for --engine datajevbench.predict:create_predict."""
    return PredictAdapter(**options)
