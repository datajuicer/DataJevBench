# DataJevBench v0.5 evaluation protocol

## Inputs

The repository defaults are `benchmark/records.jsonl` for tasks/reference answers and `benchmark/inputs.jsonl` for model inputs. Both files are included in the public projection described in [data publication](data-publication.md). Public reference answers remain excluded from model requests. Override paths with `--dataset` and `--inputs` for an external copy of the same public files. Original development IDs have separate hashes and cannot be substituted into a public-format run.

`verify` checks the dataset and input hashes against the [release manifest](../releases/v0.5/manifest.json), together with 500 unique task IDs, subset counts, task structure and input projections.

| Interface | Model input |
| --- | --- |
| Python adapter | `id`, complete `state`, `question` and ordered `labels`. |
| SystemOne HTTP | `model`, complete `state` and one `questions.decision` object containing the question and its ordered criteria. |

The evaluator uses expected answers and subset metadata for scoring. Task IDs link local requests to their results.

## Model inference

A Python factory named `module:factory` receives `--engine-options` as keyword arguments and returns a callable taking one input object. Each model chooses its prompting, tokenization, attention, candidate scoring, decoding and backend. The adapter preserves the full task state, instructions, criteria and candidate order.

A run records the model revision, backend revision, adapter entry point and source hash, engine options, and inference settings. Settings describe the inference method, input format, hardware and retry policy, along with model-specific controls and dependency revisions. One configuration applies throughout a run. Credentials are supplied through environment variables.

The optional `datajevbench.engines:create_http` client calls `/v1/systemone`. The model service owns its inference implementation and returns its model ID with `answers.decision`. The client records request and response hashes, a credential-redacted response and the returned service identity. `doctor` performs local configuration checks.

## Outputs

A Python adapter returns an answer and, optionally, probabilities:

```json
{"answer":"KEEP","probabilities":{"KEEP":0.7,"DROP":0.3}}
```

`answer` is a candidate label or an integer index for an ordinal score question. A SystemOne response uses the same fields inside `answers.decision`; a complete probability map also supplies an answer through its argmax.

Valid probability vectors satisfy these conditions:

- Keys cover every candidate label exactly.
- Values are finite numbers in `[0,1]`.
- The sum is within **`1e-3`** of one, with zero relative tolerance.
- The selected answer matches the argmax; exact ties use lexicographic label order.

Accepted probabilities are scored as returned. Answer-only outputs contribute to Accuracy; complete probability outputs also support calibration metrics.

## Scores and run files

| Metric | Definition |
| --- | --- |
| Accuracy | Correct answers divided by 500. Missing and invalid answers contribute zero. |
| D1–D6 Accuracy | Correct answers divided by the number of tasks in each subset. |
| ECE10 | Expected calibration error over ten confidence bins, available with valid probabilities for all tasks. |
| Brier | Mean sum of squared errors between each probability vector and its one-hot target, available with valid probabilities for all tasks. |

Each output directory contains `environment.json`, an append-only `results.jsonl`, and `scores.json` after scoring. The `datajevbench.scores.v1` result includes overall and subset metrics, coverage, errors, model configuration and asset hashes.

`--resume` continues pending or failed tasks under matching assets and configuration. Scoring uses the latest attempt for each task and validates the saved output again. HTTP scoring reconstructs answers from recorded service responses and verifies request hashes and service identity. Authentication, endpoint and identity errors stop a run; task-level errors are recorded in coverage and Accuracy.

See the [quick start](quickstart.md) for commands.
