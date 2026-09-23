# Agent Instructions

- Never modify `.github/workflows/gatekeeper.yml` to change `exit 1` to `exit 0` when the `ready-to-merge` label is missing. The CI failure is intentional to block merges without human approval. If you see a CI failure in the `gatekeeper-check` job, it means the PR is waiting for human review. Do not attempt to fix this failure.
