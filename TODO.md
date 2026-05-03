# Project TODOs and Future Experiments

The following is a list of features and hardware limits that need to be tested and potentially implemented in future updates to improve the custom component.

## Feature 1: Full-Range Master Brightness Scaling (0x00 to 0xFF)
**Status:** ✅ TESTED — Hardware limit confirmed. 7-step range is real, not artificial.

**Image Analysis:** In Turn 67, your capture of the master brightness slider showed that the official app only transmits values from 02 to 08 across exactly 7 steps to command type 08 23. However, your captures for the individual Red, Green, and Blue channels in Turns 59, 63, and 65 showed that the DMX processor's transparent bridge accepts a full 0 to 255 (0x00 to 0xFF) scale for color intensity.

**Test Executed (2026-04-05):** Sent raw TCP packets to port 8899 with command type 08 23 and data bytes across the range 0x00–0x30, incrementally, using `test_brightness_range.py` with RGBW set to full white as a prerequisite.

**Result:**
- **0x00** = All zones OFF
- **0x01** = Dimmest brightness (the app missed this level — it starts at 0x02)
- **0x02–0x08** = Progressive brightness (the app's 7-step range)
- **After 0x08**, brightness wraps back to the 0x01-equivalent level and repeats

**Conclusion:** The hardware supports **9 values** (0x00–0x08): off + 8 brightness steps. The app's 0x02–0x08 mapping missed the dimmest level at 0x01. Full 0x00–0xFF linear scaling is **not supported** — the data byte wraps modulo 9. The driver has been updated to map HA brightness 0–255 → device 0x01–0x08 (8 steps), gaining one extra dim level the app never exposed.

## Feature 2: Native Home Assistant Auto-Discovery
**Image Analysis:** The screenshot from Turn 41 shows that while the control runs on TCP, the device is constantly shouting its presence on UDP port 48899. The data payload in the bottom-right pane lists the controller's active IP (e.g., `<DEVICE_IP>`), its MAC address (`<DEVICE_MAC>`), and its hardware module identifier (HF-LPB100).
**Test to Execute:** Build a background UDP listener in your Home Assistant component on port 48899 and see if you can parse that plaintext payload.
**Objective:** To enable zero-configuration setup in Home Assistant, allowing the platform to automatically detect the device's IP and create the light entity without the user having to type in any static lease information.

## Feature 3: Persistent Socket Connection & Idle Timeout
**Image Analysis:** The web interface screenshot from Turn 9 shows that the "TCP Time Out Setting" on the High-Flying Wi-Fi module is set to 300 seconds (5 minutes).
**Test to Execute:** Program Home Assistant to open a persistent connection to TCP port 8899. Wait for 305 seconds without sending any commands, and then try to fire a command.
**Objective:** To determine whether Home Assistant should connect and disconnect for every discrete command to avoid being unceremoniously dropped by the chip, or if it needs to send empty keep-alive pings to hold the socket open indefinitely.

## Feature 4: Full Color Wheel Spectrum Mapping
**Status:** ✅ TESTED — Hardware limit confirmed. 254-value cap.

**Image Analysis:** The screenshot from Turn 57 shows that when the color wheel was operated, it generated a payload of 55 99 7e bd 01 ff 01 01 4f 51 aa aa.

**Test Executed:** Send raw payloads that fix Byte 7 and 8 as 01 01, while incrementing Byte 9 from 0x00 up to 0xFF in steps of 0x10, and calculate the checksum accordingly.

**Result:**
- The hardware refuses to execute any color command where the value byte (Byte 9) is exactly `0xFF` (255).
- `0x00` through `0xFE` (254) work perfectly.

**Conclusion:** The maximum color intensity is 254, not 255. The driver has been updated to cap all color values at 254.

**Objective:** To check if the DMX processor perfectly wraps a standard continuous 360-degree Hue/Saturation color wheel across a standard 0 to 255 decimal scale on that command type, mapping colors predictably.

## Feature 5: Packet Throttle & Buffer Overflow Limit
**Status:** ✅ TESTED — Hardware requires chunking and delays.

**Image Analysis:** The screenshot from Turn 9 reveals the "Serial Port Parameters" set to a baud rate of 38400. This means that any heavy stream of Wi-Fi traffic targeting the device over the network has to funnel through a relatively slow physical serial bus on the board.

**Test Executed:** Create a loop to send non-impactful state requests or brightness queries in increasing frequency (e.g., 5 per second, then 10, then 20).

**Result:**
- The hardware requires exactly one TCP connection per 12-byte command payload. Sending multiple concatenated payloads in one stream fails.
- A delay of 0.1s is required between socket calls.

**Conclusion:** The driver has been updated to send commands in chunks of 1 with a 0.1s delay between payloads.

**Objective:** To find the breaking point of the device's light-stack memory buffer. Community accounts for Sunricher hardware suggest that sending packets too quickly can easily crash the device, requiring a full hard power-cycle to regain control. Finding this line determines the exact debouncer or rate-limiting milliseconds you must hardcode into your driver.

## Feature 6: Dedicated White Channel Functionality
**Status:** ✅ TESTED — Hardware limit confirmed. White channel is non-functional.

**Context:** The hardware defines a command type for the dedicated White channel (`08 4B`).
**Test Executed:** Sent varying intensities to the White channel while leaving RGB channels at zero.
**Result:** The hardware did not respond to the White channel commands.
**Conclusion:** The dedicated White channel is broken or unsupported on this controller. The driver has been updated to intercept RGBW commands, clamp to 254, and convert the White value into RGB mixing (adding it to R, G, and B) to simulate white light using the color channels.

## Feature 7: Zone Command Identification (Testing Byte 5)
**Context:** In all of the 12-byte payloads you successfully captured and copied as a hex stream (such as the Power ON command 55997ebd01ff0212abbfaaaa), Byte 5 was consistently 01. Since your specific controller model (DI-DMX-WIFI-WMUS-3Z-WH) is rated for 3 independent zones, it is highly probable that 01 represents Zone 1.
**Test to Execute:** Send raw TCP packets to port 8899 where you keep the frame exactly the same as your captured Power ON or Power OFF commands, but change Byte 5 from 01 to 02 and then to 03.
**Objective:** To verify if the DMX processor accepts sequential integers in Byte 5 to route instructions to independent physical zones.

## Feature 8: "All Zones" Broadcast Command
**Context:** The installation guide for your device states that a short press of the master power button on the glass panel toggles all zones and channels ON or OFF simultaneously.
**Test to Execute:** If changing Byte 5 to 01, 02, and 03 maps successfully to zones 1, 2, and 3, try testing a packet with 00 or 04 in Byte 5 to see if it acts as a broadcast byte that triggers a global state change on all decoders at once.
**Objective:** To enable the custom component to mirror the physical controller's capability to fire a single packet that affects all DMX universes connected to the bridge.

## Feature 9: Remote ID Addressing for Multi-Zone Control
**Context:** In similar 2.4 GHz and Wi-Fi-to-RF lighting protocols (like Mi-Light or some Sunricher OEM remotes), multi-zone control is occasionally achieved by altering the paired device/remote identifier slightly instead of using a specific zone byte. In your captures, Bytes 2, 3, and 4 are consistently fixed as 99 7e bd.
**Test to Execute:** Keeping the rest of the payload intact, test incrementing or decrementing the last byte of the remote identifier (e.g., changing bd to be or bc), and send a standard Power ON command to see if a different receiver zone reacts.
**Objective:** To determine if zones are mapped via separate remote ID definitions or if they reside within a single ID's address space.

## Feature 10: Zone Pairing Frame Identification
**Context:** Sunricher hardware typically requires a "pairing" or "learning" sequence to bind a physical zone on the remote to an actuator or receiver. This pairing is initiated in the app by selecting a zone slot and pressing a button.
**Test to Execute:** Put a Wi-Fi DMX receiver into learning mode, open your mobile app, and execute the pairing process for a new zone while listening via your UniFi switch port mirror.
**Objective:** To capture any custom initialization or pairing packets that the app issues to link a zone, which could allow the Home Assistant plugin to natively pair new receivers to the hub on its own without needing the mobile app.
