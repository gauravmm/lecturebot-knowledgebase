# Licensing Notes

This repository contains a mix of original software, original course
materials, and third-party source documents. The top-level
[LICENSE](LICENSE) applies only to the repository's original software
and project-authored documentation unless a file or subdirectory says
otherwise.

## Covered By MIT

- Python code under `lecture_knowledge/`
- Project scripts under `scripts/`
- Repo-authored specification and progress docs under `spec/`
- Repo-authored operational notes such as `README.md` and `CLAUDE.md`

## Not Automatically Covered By MIT

- Anything under `data/raw/`
- Anything under `data/processed/`
- Any slide deck, PDF, HTML page, subtitle file, image, or dataset whose
  manifest records a different license, attribution rule, or usage note

For corpus content, treat the per-item `manifest.json` as the source of
truth for licensing and provenance.

## Important Exceptions

- `data/raw/lecturer/lectures/` contains lecturer-authored materials with
  their own per-item licenses, commonly `CC BY-SA 4.0`.
- `data/raw/ai_index/`, `data/raw/epoch_models/`, and `data/raw/owid/`
  contain third-party content with their own published licenses such as
  `CC BY-ND 4.0` or `CC BY 4.0`.
- Several corpora are public-web or IR-site source material that may be
  usable for quotation and attribution, but should not be treated as
  generally relicensed by this repository.
- `data/raw/memes/` and derived meme chunks should be treated as
  separately rights-constrained material unless and until each item is
  individually reviewed and labeled for redistribution.

## Public Repo Policy

Before pushing this repository publicly, use:

`uv run public-clean --apply`

That command removes rebuildable bulk payloads from the corpora that are
kept local for licensing reasons, while preserving manifests and fetch
scripts so other users can reconstruct the corpus themselves.
