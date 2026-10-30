# Benchmark data

The complete public v0.5 data pair is included:

| File | Content | Records |
| --- | --- | ---: |
| [records.jsonl](records.jsonl) | Tasks, reference answers and minimal source metadata | 500 |
| [inputs.jsonl](inputs.jsonl) | Matching model inputs without reference answers or provenance | 500 |

From the repository root:

```bash
python -m datajevbench verify
```

Verification checks public-file hashes, the frozen scorer, 500 unique IDs, subset counts, task structure, the gold-free input projection, deterministic public IDs and unchanged model/scoring-content fingerprints.

## Format

A task retains `id`, `family`, `state`, `question`, `labels`, `expected`, `split`, `group` and `provenance`. Candidate `labels` are the ordered available answers; `expected` is the reference answer.

Each input contains only `id`, `state`, `question` and `labels`. Python adapters use the ID to match outputs, excluding it from prompts. HTTP requests contain only `model`, `state` and `questions`. Never send whole task records to a model.

Public IDs use a subset prefix plus a 16-digit hash of the model input, for example `D1-023dca27c06a775b`. Expected answers and construction metadata are excluded from the hash. Group IDs are opaque hashes preserving the original grouping. [Publication policy](../docs/data-publication.md) explains the transformation and metadata allowlist.

## Original and public identities

[The current manifest](../releases/v0.5/manifest.json) pins public files in `files` and original files in `source_files`. [The source manifest](../releases/v0.5/source-manifest.json) remains unchanged as historical evidence. Renaming and metadata projection change file hashes while preserving task state, questions, candidate order and references.

Original data and old/new ID mappings remain with the maintainer outside this public repository. Historical model predictions are not bundled. Do not resume old-ID runs using these public files; see [reproducibility](../docs/reproducibility.md).

To use public copies stored elsewhere, pass `--dataset /path/to/records.jsonl --inputs /path/to/inputs.jsonl` to `verify`, `run` or `score`.

Project-authored contributions in both public data files use [MIT](../LICENSE). Third-party material retains its [source terms and attribution](../releases/v0.5/source-notices.md). The data license does not automatically cover repository-specific code, documentation or illustrations, whose license remains to be selected by the owner.
