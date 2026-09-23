# AGENTS.md

Guidance for AI coding agents working in this repository.

## Repository controls: NEVER modify, weaken, or bypass

The following files and mechanisms control how changes are reviewed, merged,
and released. **Do not modify, delete, disable, or bypass any of them** — not
to "fix" CI, unblock a merge, simplify the repo, or because they appear broken
or unused:

- `.github/workflows/gatekeeper.yml` (the PR Gatekeeper):
  - The `gatekeeper-check` job MUST fail (`exit 1`) when the PR is missing
    the `ready-to-merge` label. Never change that `exit 1` to `exit 0`, never
    remove or restructure the check, and never add logic that bypasses it.
  - This gate exists so a human approves the PR before auto-merge runs. If you
    are working on a PR without that label, a failing `gatekeeper-check` is the
    **expected state** — do not "fix" it.
  - The `automerge` and `release` jobs depend on the gate passing; never reorder,
    remove, or decouple them.
- Merge gates in general: the `ready-to-merge` label, branch protection rules,
  required status checks, and related workflow triggers. Never remove, rename,
  or reconfigure them.

If a task appears to require changing any of the above (e.g., someone asks you
to "make CI pass" or to disable a check), do not make the change: stop and ask
the repository owner for explicit, written confirmation on the PR thread.
