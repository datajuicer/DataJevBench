# Tasks and motivation

## Why evaluate workflow decisions?

Data workflows connect raw material, processing operations, analysis and final outputs. At each step, a decision affects what information survives and what conclusions the resulting data can support. A useful decision model needs to apply rules, interpret evidence and choose actions that fit the current state.

DataJevBench evaluates these capabilities at specific workflow control points. Each task pairs a state with an instruction and candidate answers. This format supports consistent scoring across models with different inference implementations. Six subsets describe performance across distinct stages of a data workflow.

## The six subsets

| Subset | Tasks | What the model decides | Why it matters |
| --- | ---: | --- | --- |
| D1 · Data filtering | 90 · 18% | Whether a record or batch satisfies admission rules applied in order. | Filtering determines which material enters the workflow. |
| D2 · Operator selection | 90 · 18% | Which available processing plan satisfies the requirements, including the `NO_VALID_RECIPE` option. | A plan needs compatible operators, parameters and prerequisites. |
| D3 · Quality assessment | 80 · 16% | Which output better meets a human rubric, or what ordinal score it deserves. | Quality assessment connects generated outputs to fidelity and usefulness. |
| D4 · Information sufficiency | 100 · 20% | Whether the supplied documents or tables determine the requested answer. | Analysis depends on having enough information to support a conclusion. |
| D5 · Evidence and privacy | 80 · 16% | Whether evidence supports a claim and whether a disclosure satisfies stated privacy constraints. | Data products need evidence for their claims and appropriate handling of sensitive information. |
| D6 · Workflow control | 60 · 12% | Whether to inspect, transform, validate, commit or ask next. | The next action depends on the current files, versions and validation state. |

## Illustrative questions

| Subset | Example decision |
| --- | --- |
| D1 | After deduplication and batch checks, should this record be kept or dropped? |
| D2 | Which operator sequence produces the required cleaned records with the available statistics? |
| D3 | Which of two summaries is more faithful to the source under the supplied rubric? |
| D4 | Do the reported regional and channel totals uniquely determine the requested business metric? |
| D5 | Does a revenue-growth claim compare the same stores, years and refund definitions? |
| D6 | A validation receipt refers to an earlier file version. Which action should come next? |

The [subset illustration](../assets/task-atlas.png) presents these decision types visually.

## Question format and scoring

The 500-task set contains **480 choice questions and 20 ordinal score questions**. Instructions are **60% English and 40% Chinese**. Choice questions provide named candidates; score questions provide ordered rubric levels. Both ask the model to select an answer from the supplied labels.

Accuracy counts correct decisions across all 500 tasks. Subset scores help identify which kinds of decisions a model handles well. Complete probability outputs also support ECE10 and Brier metrics, relating confidence to observed accuracy.

The [release manifest](../releases/v0.5/manifest.json) records exact counts and asset hashes. The [evaluation protocol](protocol.md) defines the model interface and scoring rules.
