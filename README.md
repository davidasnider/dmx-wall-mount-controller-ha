# DiodeLED DMX Controller for Home Assistant

![Status](https://img.shields.io/badge/status-active-blue.svg)
![HA Integration](https://img.shields.io/badge/Home%20Assistant-Integration-28B9EA.svg)
![Local API](https://img.shields.io/badge/architecture-Local%20Push-success.svg)

A native Home Assistant custom component for local, cloud-free control of **DiodeLED DI-DMX-WIFI-WMUS-3Z-WH** (and compatible OEM Sunricher) wall-mounted DMX controllers over raw TCP.

This integration connects directly via the local area network on port 8899 without relying on any cloud dependencies or the official TouchDial mobile applications.

## Installation via HACS (Recommended)

> **Note**: This is a Home Assistant **custom integration**, not an add-on. You must install it through [HACS](https://hacs.xyz/) — do **not** add this URL in the Add-on Store, or you will get a "not a valid add-on repository" error.

1. Install [HACS](https://hacs.xyz/) if you haven't already.
2. Open **HACS** from the Home Assistant sidebar.
3. Navigate to **Integrations**.
4. Click the three dots (⋮) in the top right corner and select **Custom repositories**.
5. Paste the URL of this repository (`https://github.com/davidasnider/dmx-wall-mount-controller-ha`).
6. Select Category: **Integration** and click **Add**.
7. Search for "DiodeLED DMX" in HACS, install it, and restart Home Assistant.

## Manual Installation

1. Copy the `custom_components/dmx_diodeled` directory into your Home Assistant's `custom_components` directory.
2. Restart Home Assistant.
3. Navigate to **Settings > Devices & Services > Add Integration**.
4. Search for "DiodeLED DMX Controller".
5. Enter the IP Address of the wall controller when prompted.

## Local Testing & Development

We have included a command-line interface test script `test_controller_cli.py` which allows you to send packet frames directly to the local hardware outside of the Home Assistant environment. This script will translate commands instantly to the required 12-byte hex stream format.

Requires `uv` installed for dependency abstraction.

### 1. Power State Testing

Turn the controller ON:
```bash
uv run python test_controller_cli.py power on
```
Turn the controller OFF:
```bash
uv run python test_controller_cli.py power off
```

### 2. Multi-Channel RGBW Testing

The script accepts arguments across a continuous 0-255 bounds check for Red, Green, Blue, and White channels respectfully.

Full Red:
```bash
uv run python test_controller_cli.py rgbw 255 0 0 0
```
Cyan (Full Green + Full Blue):
```bash
uv run python test_controller_cli.py rgbw 0 255 255 0
```
Muted Pastel Yellow (Red + Green + 50% White wash):
```bash
uv run python test_controller_cli.py rgbw 255 255 0 128
```

### 3. Master Brightness Mapping

Home Assistant maps brightness on a `0-255` scale, but the DMX controller strictly enforces a `0x02` to `0x08` ceiling range logic across the network segment. By testing brightness, you can verify the translation array works:

```bash
# Minimum valid brightness step
uv run python test_controller_cli.py brightness 0 

# Midpoint brightness curve translation 
uv run python test_controller_cli.py brightness 128

# Maximum ceiling output boundary
uv run python test_controller_cli.py brightness 255
```

### 4. Dynamic Programs

Test built-in controller animations natively.

Activate Rainbow Animation:
```bash
uv run python test_controller_cli.py effect rainbow
```

Change Rainbow Animation Speed (Range is 1 to 10):
```bash
# Slowest speed
uv run python test_controller_cli.py speed 1

# Max speed
uv run python test_controller_cli.py speed 10
```

> **Note**: If your controller is at a different IP address or uses a port other than `8899`, pass `--ip` and/or `--port` *before* the command.
> 
> To avoid re-typing the IP each time, you can set the `DMX_IP` environment variable: `export DMX_IP=<YOUR_CONTROLLER_IP>`
> 
> Example (Custom IP): `uv run python test_controller_cli.py --ip 192.168.1.150 power on`
> Example (Custom IP and Port): `uv run python test_controller_cli.py --ip 192.168.1.150 --port 8900 effect rainbow`
