# DataJevBench v0.5 metadata

The repository provides the evaluator, inference interfaces, task metadata, documentation and illustrations under [Apache-2.0](../LICENSE). The 500 tasks and reference answers are included in [benchmark/](../benchmark/README.md), with normalized public IDs and minimal provenance. [Source notices](../releases/v0.5/source-notices.md) describe the data's applicable terms and attribution.

Source publication revisions are recorded separately in [releases/publication.json](../releases/publication.json). Benchmark content stays at 0.5. Publication 0.5.2 changes the serialized task/input hashes through ID and metadata normalization; model-visible content, references and scorer bytes are unchanged. The original hashes remain in `source_files` and the [source manifest](../releases/v0.5/source-manifest.json). See [ID policy](data-publication.md).

Publication 0.5.3 adds the external `predict(state, questions)` bridge, shared typed-answer validation and offline response replay. Dataset, scorer and historical results are unchanged. Model runtime code and weights remain external; see [deployment](deployment.md).

Publication 0.5.4 consolidates contribution and attribution documents under `docs/`, moves source-publication hashes to `releases/publication.json`, and replaces the custom build script with declarative packaging configuration. Benchmark content and scoring are unchanged.

## Task set

The benchmark contains 500 tasks: D1 90, D2 90, D3 80, D4 100, D5 80 and D6 60. There are 480 choice questions and 20 ordinal score questions, with 300 English and 200 Chinese instructions.

The [release manifest](../releases/v0.5/manifest.json) records task, input and scorer hashes:

| Asset | SHA256 |
| --- | --- |
| Task file | `c70fdb38df9fd5329ddb226942823977cd477241678f6bb58093efe827bf3588` |
| Model inputs | `5360d9f2992558fb30729c81ecbeb9e4f55bc1b0b21b3787ad96ae98631b4c0f` |
| Scorer | `4286dd5aae0c01949b2dc75052733cf5ee0bb70c5df4142be2817fc5f8070181` |

## Scoring

v0.5 uses an absolute probability-sum tolerance of **`1e-3`**, with zero relative tolerance. Accepted probabilities are scored as returned. Matching task, input and scorer hashes identify compatible runs.

Scores describe decisions at the supplied workflow control points. The [task design](design.md) explains each subset; the [protocol](protocol.md) defines inputs, outputs and metrics.
