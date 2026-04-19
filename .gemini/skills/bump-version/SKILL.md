---
name: bump-version
description: Automates semantic version bumping and GitHub releases for the DMX integration. Use when the user wants to uprev, bump the version, or release a new version.
---

# bump-version

This skill automates the process of bumping the version in `manifest.json` and `pyproject.toml`, committing the changes, and creating a GitHub Release.

## Workflow

1.  **Read Current Version**: Read `custom_components/dmx_diodeled/manifest.json` to find the current `"version"`.
2.  **Determine New Version**:
    *   **Patch Bump**: Increment the last digit (e.g., `0.4.0` -> `0.4.1`). Use for small fixes.
    *   **Minor Bump**: Increment the middle digit and reset the last digit (e.g., `0.4.1` -> `0.5.0`). Use for larger changes or features.
    *   **CRITICAL CONSTRAINT**: NEVER automatically bump the version to `1.0.0` or higher. If a bump would result in `1.0.0`, STOP and ask the user for manual confirmation.
3.  **Update Files**: Use the `replace` tool to update the version string in:
    *   `custom_components/dmx_diodeled/manifest.json`
    *   `pyproject.toml`
    *   **Lock Update**: Run `uv lock` to update `uv.lock` with the new version.
4.  **Source Control**:
    *   Run `git add custom_components/dmx_diodeled/manifest.json pyproject.toml uv.lock`
    *   Run `git commit -m "Bump version to X.Y.Z"` (replacing X.Y.Z with the new version).
    *   Run `git push`.
5.  **GitHub Release**:
    *   Run `gh release create vX.Y.Z --title "vX.Y.Z" --generate-notes` to create the formal release for HACS.

## When to use
*   When a user says "bump the version", "uprev", "release a new version", or "do a patch/minor release".
