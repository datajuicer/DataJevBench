# Run DataJevBench v0.5

Use Python 3.10+ from the repository root. Verification, saved-run scoring and HTTP transport use the standard library. Model dependencies belong in the model's own environment.

## Install and verify

```bash
python -m pip install -e .
python -m datajevbench --help
```

The public task pair is included: `benchmark/records.jsonl` and `benchmark/inputs.jsonl`. See [benchmark data](../benchmark/README.md). Verify it before inference:

```bash
python -m datajevbench verify
```

For an external copy of the same public files, add `--dataset /path/to/records.jsonl --inputs /path/to/inputs.jsonl` to `verify`, `run` and `score`. Asset verification checks frozen hashes, task structure and the exact input projection. It does not change the files.

## Configure inference

Start your model-owned `/v1/systemone` service, then create local configuration files if they do not already exist:

```bash
cp -n configs/systemone.example.json configs/systemone.local.json
cp -n configs/inference.example.json configs/inference.local.json
```

Edit the endpoint, requested model ID and expected returned model ID in the client configuration. Replace the inference-setting descriptions with the actual method, hardware, retry policy and model controls. Credentials come from environment variables. [Deployment](deployment.md) describes HTTP and Python adapter contracts.

```bash
python -m datajevbench doctor \
  --engine datajevbench.engines:create_http \
  --engine-options configs/systemone.local.json --model-id your-model
```

This is a local configuration check, not a network or model-health test.

## Run and score

The following commands require the real dataset and a running service. Choose new output directories and actual model/backend revisions.

```bash
# Diagnostic: real inference on two tasks
python -m datajevbench run \
  --engine datajevbench.engines:create_http \
  --engine-options configs/systemone.local.json \
  --settings configs/inference.local.json \
  --model-id your-model --model-revision your-checkpoint \
  --backend systemone-http --backend-revision your-service-revision \
  --limit 2 --out runs/your-model-smoke

# Full evaluation: all 500 tasks
python -m datajevbench run \
  --engine datajevbench.engines:create_http \
  --engine-options configs/systemone.local.json \
  --settings configs/inference.local.json \
  --model-id your-model --model-revision your-checkpoint \
  --backend systemone-http --backend-revision your-service-revision \
  --out runs/your-model-v05

# Offline scoring of the full run
python -m datajevbench score --run runs/your-model-v05
```

`run` calls the model and writes `environment.json` and append-only `results.jsonl`; a provider may charge for inference. `score` writes `scores.json` containing overall/subset metrics, coverage, configuration and asset hashes. A diagnostic score still uses full benchmark denominators and is not a full measurement.

Use `run --resume` with the original arguments to retry pending or failed tasks. Assets, model configuration, adapter code and diagnostic limit must match. Successful tasks are skipped and all attempts remain in the log. Scoring uses the latest attempt for each task.

## Check the repository without model access

```bash
PYTHONDONTWRITEBYTECODE=1 python scripts/check_repo.py
```

Inference checks use synthetic fixtures, including a local HTTP test server, and do not call a real model. They validate the published result tables, source manifest, frozen scorer and included public task pair. Original unpublished data and historical predictions are not required. They do not replay historical predictions. See [reproducibility](reproducibility.md).
