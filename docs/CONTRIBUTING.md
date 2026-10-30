# Contributing

Use Python 3.10+. Run the commands below from the repository root. Keep task state, question and ordered candidates unchanged across inference implementations. The [quick start](quickstart.md) covers verification, inference and saved-run scoring; [deployment](deployment.md) describes model integration.

## Contributions

| Contribution | Include |
| --- | --- |
| Model integration | Adapter/service contract, model revision, runtime requirements and inference controls |
| New results | Model/checkpoint, `scores.json`, measurement date, settings, code revision and coverage |
| Task or scoring issue | Task ID, applicable rule, reproducible input and expected behavior |
| Documentation or tooling | User-visible behavior and relevant validation |

Use repository Issues or pull requests. Keep v0.5 content, scorer bytes and asset hashes fixed. Task corrections require a separately reviewed content version. New checkpoints receive distinct result entries.

## Checks

```bash
python -m pip install -e .
PYTHONDONTWRITEBYTECODE=1 python scripts/check_repo.py
```

Inference tests use synthetic fixtures and a local HTTP server on CPU, with outputs in temporary directories. Checks also verify the included public task pair, ID policy, source/public identities, release metadata, illustrations and document links. No model weights, historical predictions or original unpublished data are required.

## Site and illustration

`results/leaderboard.json` is the sole published result source. After changing approved results, run `python scripts/render_results.py` to update both README tables. The website reads the same JSON directly.

For a source preview, serve the **repository root** and open the site subdirectory:

```bash
python -m http.server 8000 --bind 127.0.0.1
# Open http://127.0.0.1:8000/site/
```

The site references sibling `assets/` and `results/` directories. Serving `site/` alone will not resolve them. For a standalone static export:

```bash
python scripts/build_site.py --output /tmp/datajevbench-site
python -m http.server 8000 --bind 127.0.0.1 --directory /tmp/datajevbench-site
```

The export copies only the site, public illustrations and leaderboard. Generated copies are build outputs, not additional editable result sources. Hosting is chosen separately.

Generate the shared illustration with `python scripts/atlas_illustration.py`, which requires `rsvg-convert`. The PNG is 3200 × 2240 pixels and displays at 800 × 560 in the READMEs.

## Data and releases

The public task pair is included; its format is documented in [benchmark/README.md](../benchmark/README.md). [Publication policy](data-publication.md) specifies stable IDs, minimal provenance, original/public hashes and historical-run identity. Keep the original-to-public ID mapping outside source control. Keep audits, raw runs, model weights, credentials and local deployment settings outside source control.

The content manifest remains in `releases/v0.5/manifest.json`. `releases/publication.json` is generated source-publication metadata; it excludes its own hash. After source changes, regenerate it and validate:

```bash
python scripts/release_manifest.py --write
python scripts/check_repo.py
```

Increment `PUBLICATION_VERSION` in `scripts/release_manifest.py` for a new source publication without changing the content version. Create a checked archive from a clean local commit:

```bash
python scripts/export_public.py --output /tmp/datajevbench-v0.5-source.tar.gz
```

Do not describe manifest checks or snapshot validation as historical replay. The source package does not include the historical per-task predictions; see [reproducibility](reproducibility.md).

## Packaging

`pyproject.toml` defines installation, package data and license files. It maps the existing v0.5 manifest into the installed package without a custom build script or a second source copy. `MANIFEST.in` selects the documentation, benchmark and other files included in source distributions; it is separate from the generated publication hashes. Attribution is retained in [NOTICE](NOTICE).
