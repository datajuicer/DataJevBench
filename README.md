# DataJevBench v0.5

[简体中文](README.zh-CN.md)

**500 tasks · 6 subsets · English + Chinese · v0.5**

[Design](docs/design.md) · [Results](#results) · [Quick start](#quick-start) · [Contributing](docs/CONTRIBUTING.md) · [Citation](#citation)

> Data: all 500 tasks and reference answers are included in [benchmark/](benchmark/README.md). Public IDs use `D1-<16 hex digits>`; task content and the v0.5 scorer are unchanged. See [publication and ID policy](docs/data-publication.md).

DataJevBench evaluates **decisions within data workflows**: which records to keep, which processing steps to choose, how to judge output quality, whether evidence supports an analysis, and what action to take next.

## Why these decisions?

Data quality depends on choices throughout a workflow. Filtering determines which material enters a dataset. Processing plans determine how that material is transformed. Quality checks and evidence assessment determine which outputs are useful and which conclusions are supported. Workflow control connects these decisions to the next action.

These choices require a model to combine the available material with explicit rules, quality criteria and the current workflow state. DataJevBench presents them as **500 tasks across six subsets**, covering decisions from data admission through output validation. Shared task inputs and scoring make performance comparable, while subset scores show how a model handles each kind of decision.

## What is measured?

[<img src="assets/task-atlas.png" width="800" height="560" alt="Six DataJevBench subsets with task counts, decisions and illustrative examples">](assets/task-atlas.png)

| Subset | Tasks | Share | Central question |
| --- | ---: | ---: | --- |
| D1 · Data filtering | 90 | 18% | Should this record or batch be admitted? |
| D2 · Processing plan selection | 90 | 18% | Which available operations satisfy the processing requirements? |
| D3 · Output quality assessment | 80 | 16% | How well does this output meet the quality rubric? |
| D4 · Information sufficiency | 100 | 20% | Does the available material determine the requested answer? |
| D5 · Evidence and privacy | 80 | 16% | Is a claim supported, and does a disclosure meet the privacy rules? |
| D6 · Workflow control | 60 | 12% | Which action fits the current workflow state? |

*The illustration and examples below show simplified scenarios for these six decision types.*

## Task format and coverage

Each task presents three elements:

| Element | Content |
| --- | --- |
| **State** | The material to reason over, such as records, documents, tables, operator descriptions or workflow status. |
| **Instruction** | The decision to make, together with the relevant rules or quality criteria. |
| **Candidates** | Named answer options or ordered rubric levels from which the model selects an answer. |

The task set contains **480 choice questions (96%) and 20 ordinal score questions (4%)**. Choice tasks include binary decisions, comparisons and selection among several actions or plans. Score tasks ask for a level on the supplied ordered rubric.

Instructions are **300 English (60%) and 200 Chinese (40%)**. Task materials span financial reports, scientific papers, descriptions and summaries, processing operators, and workflow states.

## Scoring

| Metric | What it describes |
| --- | --- |
| Accuracy ↑ | Correct answers divided by 500, with equal weight for each task. |
| D1–D6 Accuracy ↑ | Correct answers divided by the task count within each subset. |
| ECE10 ↓ | Agreement between confidence and observed accuracy across ten confidence bins. |
| Brier ↓ | Average sum of squared errors between predicted probabilities and the correct-answer indicator. |

The **overall score** summarizes performance across the full task distribution. **Subset scores** describe performance on individual capabilities, such as selecting a processing plan or checking evidence. Missing and invalid answers contribute zero to Accuracy. ECE10 and Brier are available when all 500 tasks have valid probability outputs.

v0.5 uses a probability-sum tolerance of **`1e-3`**. Accepted probabilities are scored as returned.

## Results

Results cover 500 tasks per model, using each model's recorded inference configuration and the v0.5 scorer. Models are ordered by **overall Accuracy**, with shared ranks for equal scores.

<!-- results:start -->

Evaluation snapshot: **2026-10-28**

| Rank | Model | Accuracy ↑ | Valid answers | ECE10 ↓ | Brier ↓ |
| ---: | --- | ---: | ---: | ---: | ---: |
| 1 | vLLM-SR d3-ultra | 83.4% | 500/500 | 0.0669 | 0.2405 |
| 2 | AutoTrust-JEV-27B v1.1 | 82.4% | 500/500 | 0.0465 | 0.2341 |
| 2 | GLiDE | 82.4% | 500/500 | 0.0309 | 0.2404 |
| 4 | vLLM-SR d3 (27B) | 81.6% | 500/500 | 0.0311 | 0.2477 |
| 5 | Mammoth-1 | 80.6% | 500/500 | 0.0483 | 0.2744 |
| 6 | Perplexity Decider v1.2 (27B) | 80.2% | 500/500 | 0.0431 | 0.2783 |
| 7 | StartLux Decision v1.1 27B Instant | 78.8% | 500/500 | 0.0442 | 0.2592 |
| 8 | Mercury Decide (Inception) | 78.4% | 500/500 | 0.1416 | 0.3600 |
| 9 | Jeffan-31B-1710 | 74.4% | 500/500 | 0.0827 | 0.3731 |
| 10 | Jev 1.14 | 73.8% | 476/500 | — | — |
| 11 | Cloudflare Clef (27B) | 73.6% | 500/500 | 0.0787 | 0.3670 |
| 12 | Microsoft Decision-1 | 72.6% | 500/500 | 0.0948 | 0.3797 |
| 13 | GPT-6 Luna Decisions | 71.2% | 500/500 | 0.1047 | 0.4162 |
| 14 | Strands Decider 26B-A4B (Gemma 4) | 60.6% | 500/500 | 0.0779 | 0.4873 |

<!-- results:end -->

Valid answers report coverage out of 500. A dash marks a calibration metric that requires complete probability coverage. The result snapshot also records D1–D6 scores, model settings, revisions and evidence hashes.

## Quick start

Python 3.10+ suffices for verification, HTTP evaluation and scoring. Models use their own inference environment. From the repository root:

```bash
python -m pip install -e .
python -m datajevbench doctor \
  --engine datajevbench.engines:create_http \
  --engine-options configs/systemone.example.json --model-id your-model
```

`doctor` checks configuration without calling a model. Tasks and reference answers are in `benchmark/records.jsonl`, with gold-free requests in `benchmark/inputs.jsonl`. Verify the included public data:

```bash
python -m datajevbench verify
```

Before inference, configure a model service and local JSON files using the [deployment guide](docs/deployment.md), then follow the [full run commands](docs/quickstart.md). HTTP uses `/v1/systemone`; a Python `module:factory` adapter is also supported. Use `--limit 2` for an initial diagnostic and a separate output directory for a full run.

Existing model implementations exposing `predict(state, questions)` can use the [predict bridge](docs/deployment.md#existing-model-implementations-with-predict), keeping model runtimes and their dependencies in the model environment.

A run saves `environment.json` and `results.jsonl`. Score an existing run with:

```bash
python -m datajevbench score --run runs/your-model-v05
```

Scoring writes `scores.json` without model calls. `run --resume` retries pending and failed tasks under matching assets and configuration, retaining all attempts.

## Contributing and reproduction

Open an **Issue** with the model/checkpoint, `scores.json`, inference settings and code revision when contributing results. For code changes, run:

```bash
PYTHONDONTWRITEBYTECODE=1 python scripts/check_repo.py
```

[results/leaderboard.json](results/leaderboard.json) is the single source for both README tables and the site. Historical per-task predictions are not bundled; checking snapshot consistency is not historical score replay. Existing scores retain their original source-data hashes; the public ID conversion did not rerun models. See [reproducibility](docs/reproducibility.md).

## Data and license

Code, documentation and illustrations use [Apache-2.0](LICENSE); attribution is retained in [NOTICE](docs/NOTICE). All 500 tasks and reference answers are included. [Data format](benchmark/README.md) documents the files and hash checks; [publication notes](docs/data-publication.md) record the original-to-public ID and metadata projection. Underlying sources retain their terms and attribution in the [source notices](releases/v0.5/source-notices.md).

## Repository guide

- **Benchmark:** [Task design](docs/design.md) · [Data directory](benchmark/README.md) · [v0.5 metadata](docs/release.md)
- **Evaluation:** [Quick start](docs/quickstart.md) · [Model deployment](docs/deployment.md) · [Scoring protocol](docs/protocol.md)
- **Results and releases:** [Result data](results/leaderboard.json) · [Reproducibility](docs/reproducibility.md) · [Source manifest](releases/publication.json) · [Site preview](docs/CONTRIBUTING.md#site-and-illustration)

## Citation

```bibtex
@misc{datajevbench,
  title = {DataJevBench: Evaluating Decisions in Data Workflows},
  author = {{DataJevBench contributors}},
  year = {2026},
  url = {https://github.com/datajuicer/DataJevBench},
  note = {Benchmark v0.5}
}
```
