---
name: bump-version
description: Automates semantic version bumping for the DMX integration. Use when the user wants to uprev, bump the version, or release a new version.
---

# bump-version

This skill automates the process of bumping the version across multiple project files and preparing a pull request. The formal GitHub Release is handled automatically by a GitHub Action when the PR is merged to `main`.

## Workflow

1.  **Read Current Version**: Read `custom_components/dmx_diodeled/manifest.json` to find the current `"version"`.
2.  **Determine New Version**:
    *   **Patch Bump**: Increment the last digit (e.g., `0.4.0` -> `0.4.1`). Use for small fixes.
    *   **Minor Bump**: Increment the middle digit and reset the last digit (e.g., `0.4.1` -> `0.5.0`). Use for larger changes or features.
    *   **CRITICAL CONSTRAINT**: NEVER automatically bump the version to `1.0.0` or higher. If a bump would result in `1.0.0`, STOP and ask the user for manual confirmation.
3.  **Update Files**: Use the `replace` tool to update the version string in:
    *   `custom_components/dmx_diodeled/manifest.json`
    *   `pyproject.toml`
    *   `README.md` (Update the `img.shields.io` version badge)
    *   **Lock Update**: Run `uv lock` to update `uv.lock` with the new version.
4.  **Source Control**:
    *   Run `git checkout -b release/vX.Y.Z` (replacing X.Y.Z with the new version).
    *   Run `git add custom_components/dmx_diodeled/manifest.json pyproject.toml README.md uv.lock`
    *   Run `git commit -m "Bump version to X.Y.Z"` (replacing X.Y.Z with the new version).
    *   Run `git push -u origin release/vX.Y.Z`.
5.  **Pull Request**:
    *   Run `gh pr create --title "Bump version to vX.Y.Z" --body "Automated version bump. A GitHub Action will trigger the formal release upon merge to main."`.

## When to use
*   When a user says "bump the version", "uprev", "release a new version", or "do a patch/minor release".
