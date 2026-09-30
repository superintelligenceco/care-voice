# 0004: Release from annotated tags instead of release-please

- Status: Accepted
- Date: 2026-09-30

## Context

The first workflows used release-please to open release pull requests and create tags. The organization does not let GitHub Actions open pull requests, so release-please failed on every push to `main`. The project also needs to build standalone executables on four operating systems, a multi-arch container image, an SBOM, checksums, and provenance attestations, and to publish to PyPI, all from the same version.

## Decision

- A pushed `v*` tag is the only release trigger.
- The release workflow checks that the tag matches the version in `pyproject.toml` and that `CHANGELOG.md` has an entry for it, then builds every artifact, attests it, publishes to PyPI, and creates the GitHub Release with notes taken from the changelog.
- The Docker workflow pushes, signs, and attests the image for the same tag.
- You bump the version and edit the changelog by hand in a normal commit before tagging.

## Consequences

- One path produces a release, and a release always has its assets.
- Maintainers write the changelog themselves instead of relying on commit messages.
- A tag that does not match the package version fails fast, before anything is published.
