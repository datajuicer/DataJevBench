# Public data and identifier policy

Publication **0.5.2** includes all 500 v0.5 tasks and reference answers. The original source pair was checked against the pre-publication hashes before conversion. Task state, question text, candidate order, expected answers, family, split, subset assignment and record order are unchanged. The frozen scorer is unchanged. Public IDs, group identifiers and non-scoring provenance use a compact publication format.

## Identifier scheme

IDs have the form `D1-023dca27c06a775b`: the D1–D6 subset plus 16 lowercase hexadecimal digits. The suffix is the first 16 digits of SHA256 over the UTF-8 canonical JSON object containing:

```text
schema = "datajevbench.public.v1"
subset = provenance.subset
state = original state
question = original question
labels = original ordered candidate names
```

Canonical JSON uses sorted object keys, compact separators, literal Unicode and finite numbers. Candidate order is explicitly represented by `labels` (and score criteria remain ordered lists). **Expected answers, old IDs, source names, construction versions, review outcomes and measured difficulty are excluded from the ID hash.** The implementation is [publication.py](../datajevbench/publication.py).

IDs are deterministic, independent of record order and reference-answer changes. Duplicate visible tasks or truncated-hash collisions abort conversion rather than receiving an order-dependent suffix. All 500 public IDs are unique. Changing model-visible content or subset produces a different ID; editing the frozen benchmark still requires a content-version decision.

The `D1` prefix intentionally reveals the subset. These identifiers remove directly readable construction cues; they are not encryption, dataset anonymization or protection against memorization of public answers. HTTP excludes IDs entirely. Python adapters receive the ID for matching responses and should exclude it from prompts.

## Metadata projection

Original identifiers exposed development versions and construction families. The original provenance also contained review tags, development-panel accuracy, template names and summaries, some of which describe the reference reasoning. These are evaluator metadata and must never enter model requests.

The public provenance retains subset, source name and URL, source terms, source/document hashes, reference type, task language and explicit human-reference caveats where present. It excludes internal source IDs, template/ancestor identifiers, import/revision markers, panel results, review tags, construction difficulty, summaries and audit notes. The original source files preserve all of that material outside the public Git repository.

`group` uses `G-` plus 16 SHA256 digits over canonical `{"schema":"datajevbench.public.v1","group":original_group}`. Equal original groups remain equal public groups; collisions are rejected. This preserves the supplied grouping, not a claim that all related variants have been independently identified. Private old/new task and group mappings support later historical-prediction imports.

## Content and result identity

- [manifest.json](../releases/v0.5/manifest.json) pins current public task/input hashes in `files` and original hashes in `source_files`.
- [source-manifest.json](../releases/v0.5/source-manifest.json) preserves the original source manifest, including its historical distribution status.
- `publication.semantic_sha256` fingerprints the ordered scoring content excluding IDs and non-scoring metadata; it was checked equal before and after conversion.
- `publication.model_wire_sha256` fingerprints ordered HTTP-visible states and questions, preserving nested candidate order; it was checked equal before and after conversion.
- [leaderboard.json](../results/leaderboard.json) retains its original source hashes and all measured values. Conversion did not call models or recreate historical predictions.

Input-file hashes change because input IDs change. Old run IDs, request hashes and environment identities therefore cannot be resumed against the public files. Future prediction migration must explicitly use the private mapping and validate all run fingerprints; do not silently rewrite historical evidence or imply a new measurement.

## Reproducing the projection

The maintainer can run the deterministic converter with the frozen original pair:

```bash
python scripts/prepare_public_data.py \
  --dataset /path/to/original/data-jevbench-v0.5.jsonl \
  --inputs /path/to/original/inputs.jsonl \
  --source-manifest releases/v0.5/source-manifest.json \
  --output /tmp/datajevbench-public-staging
```

The output must be a new directory outside this repository. It includes a private ID audit map; only the approved public pair and current release manifest belong in the public repository. Consumers can validate the included public data with `python -m datajevbench verify` without the originals or mapping.
