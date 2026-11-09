# Incoming diagnostic files

Upload diagnostic ZIP bundles here and commit them to `main`.

## Workflow

- ZIP uploads under `incoming/` (or at the repository root) automatically trigger **Inspect uploaded diagnostic archives**.
- The GitHub Actions job inventories the archive, parses JSON, and extracts important log lines, including PanVK / Kbase / CSF / Android WSI / Gralloc / AHardwareBuffer traces.
- The generated text report is stored as a GitHub Actions Artifact for 30 days. The expanded logs are not committed back into this public repository.
- A manual run is also available in Actions; set `archive_path` to a repository-relative ZIP path.

## Naming

Prefer names such as:

`20261109-zephyr-panprobe-run2.zip`

`20261110-zephyr-panplay-d3d11-smoke.zip`

Include the device, app/test and run number where practical. Before uploading, remove credentials, access tokens and unrelated personal data from logs. This repository is public.

For files larger than GitHub's normal 100 MB per-file limit, use a GitHub Release asset or Git LFS rather than committing the binary directly.
