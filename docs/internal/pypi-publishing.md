# Python Package Publishing Runbook

This repository's GitHub `publish.yml` workflow builds, validates, signs, attests,
and uploads release artifacts. It does not push packages to a public or private
Python index by itself.

## Required Pre-Publish Gates

Before any Python package artifact is uploaded to an index:

1. Build artifacts in the release workflow.
2. Run the package release validator:
   - `packages/ophanix-tool-gateway-sdk/scripts/validate_release.py`
   - `packages/product-platform/scripts/validate_release.py`
3. Preserve the workflow logs, artifact checksums, provenance attestations, and
   package SBOM.
4. Confirm that `twine check` passed for the wheel and source distribution.
5. Confirm that `release-manifest.json` is present in the artifact bundle and
   its SHA-256 checksums match the files being uploaded.
6. Confirm that the SDK vendored copy in product-platform matches the standalone
   SDK before publishing either package.
7. Confirm security review approval for any release that changes authentication,
   credential storage, response redaction, package metadata, or release tooling.

## Upload Handoff

Release owners may upload only artifacts produced by the validated workflow.
Manual rebuilds on a workstation are not release artifacts.

The upload mechanism must be one of:

- An approved internal release pipeline with artifact provenance preserved.
- PyPI trusted publishing configured for this repository and package.
- A private package index upload using short-lived credentials issued for this
  release.

Do not upload artifacts if the build job skipped validation, generated no SBOM,
or produced artifacts from an untagged or dirty release state.

## Required Evidence

Record the following in the release ticket or release notes:

- Git tag and commit SHA.
- Package names and versions.
- Wheel and source distribution filenames.
- SHA-256 checksums for every uploaded artifact.
- `release-manifest.json` contents or attachment.
- Release workflow URL.
- SBOM artifact name or attached SBOM file.
- Approver for the final package-index upload.
