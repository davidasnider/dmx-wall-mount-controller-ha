# DiodeLED DMX Controller for Home Assistant

![GitHub tag (latest by date)](https://img.shields.io/github/v/tag/davidasnider/dmx-wall-mount-controller-ha?label=version)
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

If you prefer not to use HACS, you can install the integration manually:

1. Copy the `custom_components/dmx_diodeled` directory from this repository into your Home Assistant's `custom_components` directory.
2. Restart Home Assistant.

## Adding the Device to Home Assistant

Once the integration is installed (via HACS or manually) and Home Assistant has restarted, follow these steps to add your DMX controller:

1. **Find the IP Address:** Discover the IP address of your wall controller. You can find this in your router's DHCP lease table (look for Espressif or HF-LPB100 devices) or within the official TouchDial mobile app if previously configured. **It is highly recommended to assign a static IP address** to the controller in your router to prevent connection issues if the IP changes.
2. Open Home Assistant and navigate to **Settings** > **Devices & Services**.
3. Click the **+ Add Integration** button in the bottom right corner.
4. Search for **"DiodeLED DMX Controller"** and select it. *If it doesn't appear, try clearing your browser cache or doing a hard refresh.*
5. In the configuration dialog, enter the following details:
   - **Host:** The IP address of your DMX controller on your local network (e.g., `192.168.1.50`).
   - **Port:** `8899` (This is the default port for these devices and rarely needs changing).
   - **Name:** A friendly name for your controller (default is "DiodeLED DMX").
6. Click **Submit**. Home Assistant will immediately add the controller and expose a light entity (e.g., `light.diodeled_dmx`) that you can add to your dashboards.

## Local Testing & Development

We have included a command-line interface test script `test_controller_cli.py` which allows you to send packet frames directly to the local hardware outside of the Home Assistant environment. This script will translate commands instantly to the required 12-byte hex stream format.

Requires `uv` installed for dependency abstraction.

*Note: The CLI script and the integration enforce hardware-specific constraints (e.g., maximum RGB color intensities of 254 and a 0.1s socket throttle delay) as verified in hardware testing.*

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

The script accepts arguments across a continuous 0-255 bounds check for Red, Green, Blue, and White channels respectfully. Please note that while the script accepts `0-255`, the driver enforces a maximum intensity cap of `254` due to hardware limitations on the color channels.

Additionally, the hardware's dedicated White channel (`CMD_TYPE_WHITE = [0x08, 0x4B]`) is non-functional. The driver automatically compensates for this by converting requested White values into RGB mixing (adding the White value to the Red, Green, and Blue channels, capped at 254).

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

Home Assistant maps brightness on a `0-255` scale, but the DMX controller hardware uses a `0x01` to `0x08` range (8 steps). The driver maps between them automatically:

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

## Troubleshooting & Debugging

If the integration doesn't seem to be working, here are the steps to isolate the problem:

### 1. Close the Mobile App
The hardware controller only supports **one active TCP connection at a time**. If you have the official TouchDial mobile app open on your phone, Home Assistant will be blocked from sending commands. Force-close the app and try again.

Additionally, the hardware requires commands to be sent individually (chunk size of 1) with a 0.1s delay between payloads. The integration handles this throttling and chunking automatically.

### 2. Verify Basic Connectivity with the CLI
Use the included `test_controller_cli.py` script to bypass Home Assistant entirely and test the direct network connection from your computer:
```bash
uv run python test_controller_cli.py --ip <YOUR_CONTROLLER_IP> power on
```
If this fails, the problem is at the network level:
- Ensure the IP address is correct (ping it!).
- Ensure your Home Assistant / computer is on the same network subnet/VLAN as the controller.
- Check if your router or firewall is blocking TCP port `8899`.

### 3. Enable Home Assistant Debug Logging
If the CLI works but the Home Assistant integration does not, you can enable verbose logging to see exactly what hex payloads HA is trying to send.

Add the following to your Home Assistant `configuration.yaml`:

```yaml
logger:
  default: info
  logs:
    custom_components.dmx_diodeled: debug
```

Restart Home Assistant, attempt to turn the light on/off from the dashboard, and then check `Settings` > `System` > `Logs` (or view the `home-assistant.log` file directly). You will see the exact connection attempts and byte arrays being sent.

*Note: As thoroughly tested, the hardware limits are verified; full-range color intensity mapping (0x00 to 0xFF) was tested and found unsupported, strictly wrapping modulo 9 or capping at 254 depending on the command type.*
