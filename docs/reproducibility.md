# Data and reproducibility

## Content version and source publication

The benchmark content version is **v0.5**: 500 tasks across D1–D6 and a frozen scoring contract. [releases/v0.5/manifest.json](../releases/v0.5/manifest.json) pins task bytes, model-input bytes and scorer bytes. [MANIFEST.json](../MANIFEST.json) separately identifies the source publication, hashes its files and records data availability. Changing directories or documentation does not create new benchmark content.

The approved public data paths are `benchmark/records.jsonl` and `benchmark/inputs.jsonl`. Both files are included. Public IDs and non-scoring metadata were normalized without changing task content or references. The current manifest pins the public files, preserves original hashes in `source_files`, and records equal semantic and HTTP-visible request digests. The immutable [source manifest](../releases/v0.5/source-manifest.json) identifies the original data pair. Reference answers remain outside model requests even when publicly available.

## Published snapshot

[results/leaderboard.json](../results/leaderboard.json) is the authoritative published snapshot. Both README tables and the website use this data. It records overall and subset scores, valid probability coverage, inference settings, model identities and evidence hashes. Existing measurements retain their original dates, scores and source-data hashes. The snapshot validator uses the manifest's `source_files` identities for these historical rows. New public-ID runs use the current public hashes. The ID conversion is not a new inference measurement.

The source package does not contain the historical per-task predictions or raw runs. Hashes identify evidence but cannot reconstruct it. `python scripts/render_results.py --check` validates table consistency and score aggregates; it does not rerun inference or reproduce historical scores from predictions. There is no historical `replay` command or downloadable prediction archive promised by this source release.

## Recompute your own saved run

```bash
python -m datajevbench verify
python -m datajevbench score --run runs/your-model-v05
```

This requires the real task pair plus the run's `environment.json` and `results.jsonl`. Scoring revalidates outputs, inputs and run identity; built-in HTTP and predict-bridge runs also reconstruct normalized answers from saved responses. It writes `scores.json` without model calls or loading external model code. A fresh `run` invokes the configured model and is a different operation.

Do not resume an original-ID run with the public-ID dataset. A future historical-prediction import needs the maintainer's ID mapping and explicit migration of run fingerprints; simply replacing IDs inside a log is insufficient. Original data and the private mapping remain outside the public repository.

Resume requires matching assets and configuration. Successful tasks are retained; pending and failed tasks are attempted again. The append-only log retains each attempt and scoring uses the latest attempt per task. Report recovery policies when comparing runs.

## Reporting results

Include benchmark version, source publication or Git revision, dataset/input/scorer hashes, model and checkpoint revision, backend revision, inference settings, measurement date and valid/expected coverage. Share `scores.json` with an Issue and enough adapter or service information to explain the inference method. Review raw responses for private content before sharing them.

Accuracy always uses all 500 tasks; missing and invalid answers count as incorrect. ECE10 and Brier require valid probabilities on all 500 tasks. Partial runs are diagnostics and must not be presented as complete benchmark measurements. [Protocol](protocol.md) specifies the frozen probability rules and subset denominators.

## Scope and limitations

The benchmark measures decisions from supplied states and candidates. It does not by itself measure end-to-end data-pipeline success, model-serving latency or production cost. Publication of reference answers does not establish a hidden test split or absence of training overlap. Source-specific data terms and attribution remain in the [source notices](../releases/v0.5/source-notices.md).
