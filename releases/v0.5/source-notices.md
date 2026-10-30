# Data sources and terms

Task provenance records source identifiers and applicable terms. Counts are mutually exclusive across the source families below; material included through CDRBench is counted once.

| Source | Tasks | Subsets | Recorded terms |
| --- | ---: | --- | --- |
| [CDRBench](https://arxiv.org/abs/2606.31435) | 49 | D1: 26, D2: 3, D3: 20 | Academic noncommercial use under source-specific authorization. Preserve attribution for CC-BY-4.0 upstream materials and underlying source rights. |
| [Data-Juicer](https://github.com/datajuicer/data-juicer) | 87 | D2: 87 | Apache-2.0 operator code and documentation; associated task scenarios and fixtures are separately authored. |
| [FinQA](https://github.com/czyssrs/FinQA) | 49 | D1: 9, D4: 20, D5: 20 | MIT repository; underlying annual reports retain their source rights and attribution. |
| [QASPER](https://allenai.org/data/qasper) | 12 | D4: 12 | CC-BY-4.0 dataset; original paper rights retained. |
| [SFHOT/SFRES](https://github.com/jeknov/EMNLP_17_submission) | 30 | D3: 30 | MIT repository annotations; source text retains its original attribution. |
| [SummEval](https://github.com/Yale-LILY/SummEval) | 30 | D3: 30 | MIT repository annotations; underlying news text retains its source rights and attribution. |
| Data workflow scenarios | 243 | D1: 55, D4: 68, D5: 60, D6: 60 | Authored benchmark tasks and synthetic workflows, subject to source-specific authorization and attribution, including [FinQA](https://github.com/czyssrs/FinQA). |

Project-authored contributions to the benchmark data are licensed under [MIT](../../LICENSE). This grant does not replace the source terms above, including academic noncommercial restrictions and attribution requirements, or grant rights in third-party material that the project does not hold. Repository-specific code, documentation and illustrations still need an owner-selected license; data permission does not automatically license those files. All 500 tasks and reference answers are published under `benchmark/`. The public projection preserves source attribution, license text and source hashes while moving construction/audit metadata out of the public records. See [data availability](../../benchmark/README.md) for the expected files and verification steps.
