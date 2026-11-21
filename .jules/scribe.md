# Scribe journal

## 2026-11-21 - README config-form default name was wrong
**Learning:** Config-flow defaults live in `const.py` (`DEFAULT_NAME`, `DEFAULT_PORT`) and are wired into the form schema in `config_flow.py`. When checking README install steps, compare them against those constants — the "Manual" section's Name default ("DiodeLED DMX") had drifted from `DEFAULT_NAME` ("DiodeLED DMX Controller"). Other README claims verified correct as of this run: TCP default port 8899, discovery UDP 48899 (discovery.py), `DMX_IP` env var in test_controller_cli.py, HA 2025.11 requirement (hacs.json), brand/ icons present.
