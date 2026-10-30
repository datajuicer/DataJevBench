# Model deployment and adapters

The evaluator supports a model-owned SystemOne HTTP service or an in-process Python adapter. Model weights, upstream runtimes and credentials are supplied separately. The repository does not bundle model-specific servers. Configure prompting, tokenization, attention, calibration and device placement in the model implementation; the benchmark preserves the input and scoring contract.

## HTTP service

Start a service exposing `POST /v1/systemone` in the model's environment. The evaluator sends:

```json
{
  "model": "your-model",
  "state": "The complete supplied task state",
  "questions": {
    "decision": {
      "type": "choice",
      "instructions": "Choose the action supported by the state.",
      "criteria": {"KEEP": "Keep the record", "DROP": "Drop the record"}
    }
  }
}
```

The response identifies the actual service model and returns its answer:

```json
{
  "model": "your-model-revision",
  "answers": {
    "decision": {
      "answer": "KEEP",
      "probabilities": {"KEEP": 0.7, "DROP": 0.3}
    }
  }
}
```

These objects illustrate the wire format, not a released task. Preserve the actual question type, state, instructions and candidate order. Complete probabilities can supply an answer through argmax; answer-only responses support Accuracy. Typed Choice (`choice`) and Score (`score`, `probabilities`) responses are supported. Score is an expectation, so Score responses require probabilities to select a benchmark label. Ties use lexical label order; probabilities are never renormalized. See [response validation](protocol.md#outputs) for all rules.

Copy [systemone.example.json](../configs/systemone.example.json) to `configs/systemone.local.json`. Replace the endpoint and requested `model_id`, and pin the actual response identifier with `expected_returned_models`. Use the same requested model ID in `--model-id`. If authentication is required, set the client's `key_env` to the name of an environment variable holding the service credential. Hosted-provider credentials belong in the model service.

Configure the final endpoint URL: HTTP redirects are rejected without retrying to prevent forwarding credentials to another address.

Copy [inference.example.json](../configs/inference.example.json) to `configs/inference.local.json` and replace its descriptions with the actual inference settings. Both local configuration files are Git-ignored.

```bash
python -m datajevbench doctor \
  --engine datajevbench.engines:create_http \
  --engine-options configs/systemone.local.json --model-id your-model
```

`doctor` checks the HTTP configuration without a request, model load or GPU allocation. A successful check does not establish service health. See [quick start](quickstart.md) for a two-task smoke run and full evaluation.

## Python adapter

The engine selector is `module:factory`. The factory receives `--engine-options` as keyword arguments and returns a callable. That callable receives `{id, state, question, labels}` and returns `{answer, probabilities?}`. Keep expected answers and provenance out of prompts; the local ID is only for matching outputs.

The [example adapter](../examples/example_adapter.py) returns the first candidate and exists only to exercise the interface. It is not a benchmarked model. A diagnostic run with the included public tasks can use:

```bash
python -m datajevbench run \
  --engine examples.example_adapter:create \
  --settings examples/example-settings.json \
  --model-id first-label-demo --model-revision example-v1 \
  --backend python --backend-revision example-v1 \
  --limit 2 --out runs/adapter-smoke
```

Use the model's Python environment for a real adapter. This runner calls the adapter serially; the model implementation owns inference controls. Document its retry behavior explicitly. `--resume` retries failed tasks and retains every attempt; successful tasks are skipped. It is not equivalent to a fresh model run.

## Run identity

Each run records model and backend revisions, adapter source hash, options and inference settings. HTTP receipts also record request/response hashes and the returned service identity. Declared identity changes stop a run; unchanged identifiers cannot prove that a hosted provider kept hidden weights unchanged. Unknown revisions should be reported as unknown.

## Existing model implementations with `predict`

Use `--engine datajevbench.predict:create_predict` to load an external factory returning an object with `predict(state, questions)`. It receives only the complete state and `{"decision": question}`. The bridge preserves candidate order and delegates all model-specific compilation, tokenization and inference to that implementation. It converts typed answers to benchmark labels and saves the complete returned object under `_predict_response` for offline scoring. The backend must return JSON-serializable, credential-free output and redact its errors and receipts.

Copy [predict.example.json](../configs/predict.example.json) to `configs/predict.local.json`. `factory` names an importable class or factory; `factory_options` supplies its keyword arguments. `source_files` lists additional compiler, runtime and configuration files to fingerprint. The factory module is fingerprinted automatically. These hashes enter run identity and prevent resuming after a tracked source change. Transitive imports and weights are not automatically hashed: list relevant sources and pin checkpoint and environment revisions separately.

### Adapter handoff reviewed on 2026-10-30

The supplied source bundle contains 17 model configurations. Its 249 manifest file hashes were verified; ZIP SHA-256 is `965a058b7e6c4009055362852cd8c48ec0254a2a7b8ca28a4774bcb8cec19948`. The bundle remains external: it includes model-specific runtimes with separate licenses and some wrappers whose redistribution terms are unresolved. No new model results are implied by this integration.

| Model family | External entry point | Construction / constraints |
| --- | --- | --- |
| D3 / PPLX | `expansion_access:Native` | `c=<model config>`; original native reader |
| Clef / Strands | `jev_access.local:ClefAdapter` / `StrandsAdapter` | `c=<model config>`; use `evaluated` profile |
| GLiDE / D3 Ultra / Jeffan / Mammoth / AutoTrust | `native:Native` | `kind=glide/d3-ultra/jeffan/mammoth/autotrust`; complete snapshot required |
| StartLux | `jev_access.startlux:StartLuxAdapter` | `config=<model config>, endpoint=<service URL>`; model-owned service |
| Mercury / Jev / Luna / Microsoft | Built-in `datajevbench.engines:create_http` | Provider's SystemOne endpoint and pinned returned model ID |
| Piccolo 4B / 9B / 27B | `blink:Blink` through a local factory | Set external reference/checkpoint paths before construction; preserve compiler and attention implementation |

Unpack the handoff outside the repository on the model host. Keep its layout and use its `CONSTRUCTION.md` and per-model requirements to set up the model environment. For the GLiDE example, expose the original entry point:

```bash
export ADAPTER_BUNDLE=/path/to/datajevbench-adapter-handoff
export PYTHONPATH="$ADAPTER_BUNDLE/adapters/workspace/harnessjevbench-release-tools/p0-five-20261028${PYTHONPATH:+:$PYTHONPATH}"
```

Install the benchmark package into that environment. The supplied example uses `native:Native(kind="glide")`; fill in `source_files` with the actual runtime/compiler files before a measured run. Its constructor verifies checkpoint files against the original download plan. The source-only handoff cannot satisfy this check until the full checkpoint is available.

For a config-driven adapter such as Clef, expose `unified-p0-20261019/access` on `PYTHONPATH` and generate options from its supplied configuration (with actual checkpoint paths):

```python
import json
from pathlib import Path

config_path = Path("/path/to/clef.local.json")
options = {
    "factory": "jev_access.local:ClefAdapter",
    "factory_options": {"c": json.loads(config_path.read_text())},
    "source_files": [str(config_path), "/path/to/jev_access/common.py",
                     "/path/to/checkpoint/joint_schema_model.py"],
}
Path("configs/predict.local.json").write_text(json.dumps(options, indent=2) + "\n")
```

Use the [run commands](quickstart.md) with the predict engine and these options, documenting the actual model, settings and revisions. Start with `--limit 2` and a separate output directory. `doctor` does not load or validate external factories; a real smoke run is still required.

Keep the handoff's evaluated profile: Strands uses temperature 1 with per-kind calibration disabled; PPLX may select a cache override that needs separate weight verification; AutoTrust's Score extension and Piccolo's compiler/readout are model-specific. The handoff gateway's default Harness engine is not the historical Data adapter; explicitly inject the correct Data engine if using that gateway. Avoid adding a second retry layer. Historical API runs used concurrency 4, while this evaluator is serial. Record this difference when reporting measurements.

Verification here covers CPU interface tests, saved-response replay and source identity checks. GPU inference, checkpoint/tokenizer equivalence, provider availability and historical score reproduction require the model environment and remain unverified.
